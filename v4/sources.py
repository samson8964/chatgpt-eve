"""Independent V4 complete-universe upstream snapshot acquisition.

EVE Ref supplies full-space snapshots when timely. Each invocation downloads
a newly advertised snapshot; cached artifacts may be reused ONLY when server
metadata validates freshness, never because the previous scan used them.
Reports source timestamp and explicit completeness to avoid stale pretending LIVE.
"""
from __future__ import annotations
import bz2
import http.client
import json
import hashlib
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

MARKET_INDEX = 'https://data.everef.net/market-orders/index.json'
CONTRACT_INDEX = 'https://data.everef.net/public-contracts/index.json'
UA = 'EVE-V4 full-market research scanner (github.com/samson8964/chatgpt-eve)'
MARKET_REQUIRED = {'location_id', 'type_id', 'price', 'is_buy_order', 'volume_remain', 'order_id'}
CONTRACT_REQUIRED = {'contract_id', 'start_location_id', 'price', 'type'}


class SourceError(RuntimeError):
    pass


def _get(url: str, *, stream=False, tries=3):
    last = None
    for attempt in range(tries):
        try:
            r = requests.get(url, headers={'User-Agent': UA, 'Accept': '*/*'},
                             timeout=(15, 150), stream=stream)
            if r.status_code in (420, 429, 500, 502, 503, 504):
                raise SourceError('upstream HTTP %s' % r.status_code)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
        except SourceError as e:
            last = e
        if attempt + 1 < tries:
            time.sleep(min(15, (attempt + 1) * 3))
    raise SourceError('SOURCE_FETCH_FAILED: %s' % type(last).__name__) from last


def advertised(index_url: str, *, max_age_hours: float) -> dict:
    index = _get(index_url).json()
    files = index.get('files') or []
    if not files:
        raise SourceError('MISSING_ADVERTISED_SNAPSHOT')
    latest = max(files, key=lambda f: str(f.get('last_modified') or ''))
    stamp = str(latest.get('last_modified') or '')
    try:
        dt = datetime.fromisoformat(stamp.replace('Z', '+00:00')).astimezone(timezone.utc)
    except Exception as e:
        raise SourceError('UNKNOWN_SNAPSHOT_AGE') from e
    age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    if age > max_age_hours or age < -0.08:
        raise SourceError('STALE_SNAPSHOT: %.2fh age, threshold %.2fh' % (age, max_age_hours))
    url = latest.get('url') or ''
    if not url.startswith('https://'):
        raise SourceError('SNAPSHOT_URL_NOT_HTTPS')
    return dict(url=url, last_modified=stamp, age_hours=round(age, 3),
                fetched_at=datetime.now(timezone.utc).isoformat())


def _check_complete_bz2(path: Path) -> None:
    """Check CRC and EOF before a snapshot can become the official file.

    A full HTTP response can still contain a truncated or invalid bzip2
    stream. Handles concatenated bzip2 streams without retaining decompressed
    market rows in memory.
    """
    decoder = bz2.BZ2Decompressor()
    read_any = False
    try:
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(256 * 1024), b''):
                pending = chunk
                while pending:
                    if decoder.eof:
                        decoder = bz2.BZ2Decompressor()
                    decoder.decompress(pending)
                    read_any = True
                    pending = decoder.unused_data if decoder.eof else b''
        if not read_any or not decoder.eof:
            raise SourceError('SNAPSHOT_BZ2_INCOMPLETE_EOF')
    except (EOFError, OSError) as exc:
        raise SourceError('SNAPSHOT_BZ2_INVALID:' + type(exc).__name__) from exc


def download_fresh(source: dict, path: Path, *, attempts: int=4) -> dict:
    """Download anew on a broken *stream*, never resume unknown content.

    Each attempt opens the same advertised immutable snapshot URL with a
    NEW response, NEW sha256 and truncated .part. The final file is replaced
    atomically ONLY after HTTP length and bzip2 CRC/EOF validation pass.
    Never silently fall back to yesterday's data after all attempts fail.
    """
    if attempts < 1 or attempts > 8:
        raise ValueError('INVALID_DOWNLOAD_ATTEMPTS')
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.part')
    last = None
    for attempt in range(1, attempts + 1):
        digest = hashlib.sha256()
        n = 0
        length = None
        try:
            with _get(source['url'], stream=True) as response, temp.open('wb') as fh:
                advertised_length = response.headers.get('Content-Length')
                if advertised_length is not None:
                    try:
                        length = int(advertised_length)
                    except (TypeError, ValueError):
                        raise SourceError('SNAPSHOT_INVALID_CONTENT_LENGTH') from None
                    if length < 1024:
                        raise SourceError('SNAPSHOT_TOO_SMALL_CONTENT_LENGTH')
                for block in response.iter_content(1024 * 1024):
                    if block:
                        n += len(block)
                        digest.update(block)
                        fh.write(block)
            if n < 1024:
                raise SourceError('SNAPSHOT_TOO_SMALL')
            if length is not None and n != length:
                raise SourceError('SNAPSHOT_CONTENT_LENGTH_MISMATCH')
            _check_complete_bz2(temp)
            temp.replace(path)
            return dict(source, sha256=digest.hexdigest(), compressed_bytes=n,
                        local_file=str(path), download_attempts=attempt,
                        download_retries=attempt-1, bz2_crc_and_eof_verified=True)
        except (requests.exceptions.RequestException, http.client.IncompleteRead,
                SourceError) as exc:
            # Reopen the whole advertised URL. Do not stitch content from
            # different HTTP responses, use Range or accept a partial file.
            last = exc
            if attempt == attempts:
                raise SourceError(
                    'SOURCE_STREAM_RETRY_EXHAUSTED:' + type(exc).__name__
                ) from exc
            time.sleep(min(20, 2 ** attempt))
        finally:
            temp.unlink(missing_ok=True)
    raise SourceError('SOURCE_STREAM_RETRY_EXHAUSTED:' +
                      (type(last).__name__ if last else 'UNKNOWN'))


def market_dataframe(path: Path) -> pd.DataFrame:
    # Whole advertised data file; do not use head(n), TOP-N, previous seen IDs.
    result = pd.read_csv(path, compression='bz2', low_memory=False)
    missing = MARKET_REQUIRED - set(result.columns)
    if missing:
        raise SourceError('MARKET_SCHEMA_MISSING:' + ','.join(sorted(missing)))
    if result.empty:
        raise SourceError('MARKET_SNAPSHOT_EMPTY')
    return result


def contract_dataframes(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    with tarfile.open(path, mode='r:bz2') as arc:
        names = arc.getnames()
        c = next((x for x in names if x.rstrip('/').endswith('contracts.csv')), None)
        i = next((x for x in names if x.rstrip('/').endswith('contract_items.csv')), None)
        if not c or not i:
            raise SourceError('CONTRACT_ARCHIVE_SCHEMA_MISSING')
        contracts = pd.read_csv(arc.extractfile(c), low_memory=False)
        items = pd.read_csv(arc.extractfile(i), low_memory=False)
    missing = CONTRACT_REQUIRED - set(contracts.columns)
    if missing:
        raise SourceError('CONTRACT_SCHEMA_MISSING:' + ','.join(sorted(missing)))
    if contracts.empty:
        raise SourceError('CONTRACT_SNAPSHOT_EMPTY')
    return contracts, items
