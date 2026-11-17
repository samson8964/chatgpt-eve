"""Official ESI *regional daily trade history* reference, never a Jita fill.

EVE ESI has no per-station trade tape or exact last executed trade price.
The latest completed day with traded volume in The Forge (10000002) supplies
an explicitly labelled DAY-AVERAGE historical *research* quote. This must
never be called a Jita 4-4 execution price or a live sellable bid.

An explicit standalone refresh downloads EVE Ref's daily archives of the
official regional ESI market-history feed. Scheduled scans NEVER fetch here.
No credentials, SMTP, orders, or SQLite writes.
"""
from __future__ import annotations

import bz2
import csv
import io
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

FORGE_REGION_ID = 10000002
WINDOW_DAYS = 90
CACHE = Path("reference/forge-regional-history-latest.json")
SOURCE = "EVE_REF_ARCHIVE_ESI_FORGE_REGIONAL_DAILY_TRADE_AVERAGE"
BASIS = "THE_FORGE_LATEST_TRADED_DAY_AVERAGE_NOT_JITA_STATION_OR_LAST_TRADE"
MAX_CACHE_AGE_DAYS = 3
MAX_COMPRESSED_BYTES = 4_000_000
BOOTSTRAP_ARCHIVES = Path("reference/forge-history-bootstrap-archives")
MAX_RESUME_AGE_SECONDS = 86400


def _positive(value):
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return n if math.isfinite(n) and n > 0 else None


def _parse_day(payload: bytes, day: date) -> dict[int, dict]:
    if not isinstance(payload, bytes) or len(payload) > MAX_COMPRESSED_BYTES:
        raise ValueError("HISTORY_ARCHIVE_SIZE_INVALID")
    try:
        decoded = bz2.decompress(payload).decode("utf-8-sig")
        stream = csv.DictReader(io.StringIO(decoded))
        cols = set(stream.fieldnames or ())
        if not {"region_id", "type_id", "average", "volume"}.issubset(cols):
            raise ValueError("HISTORY_ARCHIVE_COLUMNS_INVALID")
        out = {}
        for row in stream:
            if int(row["region_id"]) != FORGE_REGION_ID:
                continue
            typ = int(row["type_id"])
            price = _positive(row.get("average"))
            volume = int(row["volume"])
            orders = int(row.get("order_count") or 0)
            if typ <= 0 or price is None or volume <= 0 or orders <= 0:
                continue
            if row.get("date") and row["date"][:10] != day.isoformat():
                raise ValueError("HISTORY_ARCHIVE_DATE_MISMATCH")
            if typ in out:
                raise ValueError("HISTORY_ARCHIVE_DUPLICATE_FORGE_TYPE")
            out[typ] = {"price": price, "date": day.isoformat(),
                        "volume": volume, "order_count": orders}
        return out
    except (OSError, EOFError, UnicodeError, csv.Error) as exc:
        raise ValueError("HISTORY_ARCHIVE_DECODE_INVALID") from exc


def load(root: Path, *, now: date | None = None) -> dict[int, dict]:
    """Fail closed on missing/stale/wrong-region cache, no network."""
    path = Path(root) / CACHE
    if not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        today = now or datetime.now(timezone.utc).date()
        built = date.fromisoformat(str(obj.get("built_on")))
        if (obj.get("schema") != 1 or obj.get("region_id") != FORGE_REGION_ID
                or obj.get("source") != SOURCE
                or not 0 <= (today - built).days <= MAX_CACHE_AGE_DAYS
                or not isinstance(obj.get("quotes"), dict)):
            return {}
        values = {}
        for typ, quote in obj["quotes"].items():
            if not isinstance(quote, dict):
                continue
            price = _positive(quote.get("price"))
            traded = date.fromisoformat(str(quote.get("date")))
            age = (today - traded).days
            if (int(typ) > 0 and price is not None
                    and 1 <= age <= WINDOW_DAYS
                    and int(quote.get("volume") or 0) > 0):
                values[int(typ)] = {**quote, "region_id": FORGE_REGION_ID,
                                    "basis": BASIS, "age_days": age}
        return values
    except (OSError, ValueError, TypeError, OverflowError):
        return {}


def _existing_for_merge(root: Path, today: date) -> dict[str, dict]:
    """Read trustworthy prior data even after its scan-use TTL expired."""
    path = Path(root) / CACHE
    if not path.is_file():
        raise ValueError("FORGE_HISTORY_INITIAL_FULL_REFRESH_REQUIRED")
    try:
        obj = json.loads(path.read_text("utf-8"))
        if (obj.get("schema") != 1 or obj.get("region_id") != FORGE_REGION_ID
                or obj.get("source") != SOURCE
                or not isinstance(obj.get("quotes"), dict)):
            raise ValueError("FORGE_HISTORY_OLD_CACHE_UNTRUSTED")
        valid = {}
        for typ, info in obj["quotes"].items():
            if not isinstance(info, dict):
                continue
            price = _positive(info.get("price"))
            traded = date.fromisoformat(str(info.get("date")))
            if (int(typ) > 0 and price is not None
                    and int(info.get("volume") or 0) > 0
                    and 1 <= (today-traded).days <= WINDOW_DAYS):
                valid[str(int(typ))] = info
        return valid
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        raise ValueError("FORGE_HISTORY_OLD_CACHE_UNTRUSTED") from exc


def refresh(root: Path, *, days: int = WINDOW_DAYS, today: date | None = None,
            fetch=None, workers: int = 4, merge_existing: bool = False,
            resume_archives: bool = False) -> dict:
    """Explicit slow data preparation; NEVER invoked from shadow scanning.

    Retrieve completed days only. If current publisher snapshots are missing,
    keep the old cache untouched and return an error (no fabricated quote).
    """
    if not 1 <= days <= WINDOW_DAYS or not 1 <= workers <= 6:
        raise ValueError("HISTORY_REFRESH_BOUNDS_INVALID")
    if resume_archives and merge_existing:
        raise ValueError("HISTORY_RESUME_AND_INCREMENTAL_CONFLICT")
    today = today or datetime.now(timezone.utc).date()
    # Never let a missing/invalid base cache truncate historical coverage.
    old_quotes = _existing_for_merge(root, today) if merge_existing else {}
    def download(day):
        url = ("https://data.everef.net/market-history/"
               + str(day.year) + "/market-history-" + day.isoformat()
               + ".csv.bz2")
        saved = Path(root) / BOOTSTRAP_ARCHIVES / (
            "market-history-" + day.isoformat() + ".csv.bz2")
        if resume_archives and saved.is_file():
            try:
                from time import time
                if 0 <= time() - saved.stat().st_mtime <= MAX_RESUME_AGE_SECONDS:
                    blob = saved.read_bytes()
                    parsed = _parse_day(blob, day)
                    return day, parsed
            except (OSError, ValueError, EOFError):
                pass  # Invalid prior archive is re-fetched, never trusted.
        if fetch:
            blob = fetch(url)
        else:
            response = requests.get(
                url, timeout=(10, 25), headers={"User-Agent":
                "V4 EVE history research / github.com/samson8964/chatgpt-eve"})
            if response.status_code == 404:
                return day, None
            response.raise_for_status()
            blob = response.content
        parsed = _parse_day(blob, day)
        if resume_archives:
            saved.parent.mkdir(parents=True, exist_ok=True)
            temp = saved.with_suffix(".bz2.part")
            try:
                temp.write_bytes(blob)
                os.replace(temp, saved)
            finally:
                temp.unlink(missing_ok=True)
        return day, parsed
    days_to_fetch = [today - timedelta(days=n) for n in range(1, days + 1)]
    fetched = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(download, day): day for day in days_to_fetch}
        done = 0
        for task in as_completed(jobs):
            day, records = task.result()
            done += 1
            if records is not None:
                fetched[day] = records
            if done % 5 == 0 or done == len(jobs):
                print(f"FORGE_HISTORY_ARCHIVE_PROGRESS {done}/{len(jobs)} "
                      f"available={len(fetched)}", flush=True)
    recent = [d for d in fetched if (today-d).days <= 3]
    if not recent or not any(fetched[d] for d in recent):
        raise ValueError("FORGE_HISTORY_RECENT_PUBLISHER_MISSING")
    # A daily 5-day incremental refresh may encounter 1-2 unpublished
    # recent archives. Require at least 3 published days and a recent
    # Forge trade instead of failing the whole cache solely on publisher lag.
    minimum_days = min(days, 3) if merge_existing else min(days, 5)
    if len(fetched) < minimum_days:
        raise ValueError("FORGE_HISTORY_ARCHIVE_COVERAGE_INCOMPLETE")
    quotes = dict(old_quotes)
    for day in sorted(fetched):
        for typ, info in fetched[day].items():
            key = str(typ)
            prior = quotes.get(key)
            if prior is None or str(prior["date"]) <= day.isoformat():
                quotes[key] = info  # Newer trade day or in-place correction.
    quotes = {key: value for key, value in quotes.items()
              if 1 <= (today - date.fromisoformat(value["date"])).days
              <= WINDOW_DAYS}
    if not quotes:
        raise ValueError("FORGE_HISTORY_NO_REPORTED_TRADES")
    path = Path(root) / CACHE
    path.parent.mkdir(parents=True, exist_ok=True)
    result = {"schema": 1, "region_id": FORGE_REGION_ID,
              "source": SOURCE, "built_on": today.isoformat(),
              "window_days": WINDOW_DAYS,
              "refresh_mode": ("INCREMENTAL_5_DAY_MERGE" if merge_existing
                               else "FULL_REBUILD"),
              "days_available": len(fetched),
              "latest_archive_date": max(fetched).isoformat(),
              "quotes": quotes}
    tmp = path.with_suffix(".json.part")
    try:
        tmp.write_text(json.dumps(result, ensure_ascii=False,
                                  separators=(",",":"),allow_nan=False),
                       encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return {"status": "FORGE_HISTORY_CACHE_PREPARED_NOT_STATION_TRADES",
            "latest_archive_date": result["latest_archive_date"],
            "days_available": len(fetched), "types_with_history": len(quotes),
            "refresh_mode": result["refresh_mode"],
            "cache": str(path)}


def main():
    from argparse import ArgumentParser
    p = ArgumentParser(description="Explicit 90-day regional trade-history cache")
    p.add_argument("--data-root", type=Path,
                   default=Path.home()/"EVE-V4-Data")
    methods = p.add_mutually_exclusive_group()
    methods.add_argument("--refresh", action="store_true",
                         help="Full initial/weekly 90-day rebuild")
    methods.add_argument("--refresh-incremental", action="store_true",
                         help="Daily five-day update; merge prior 90 days")
    methods.add_argument("--refresh-auto", action="store_true",
                         help="Daily scheduled: full on Sundays or first run, else 5-day merge")
    methods.add_argument("--refresh-resumable", action="store_true",
                         help="One-time 90-day bootstrap with per-day resumable archive files")
    p.add_argument("--days", type=int, default=WINDOW_DAYS)
    p.add_argument("--workers", type=int, default=2,
                   help="Network requests in parallel; 2 is gentler for unstable links")
    args = p.parse_args()
    if args.refresh:
        result = refresh(args.data_root, days=args.days,
                         workers=args.workers)
    elif args.refresh_resumable:
        result = refresh(args.data_root, days=args.days,
                         workers=args.workers, resume_archives=True)
    elif args.refresh_incremental:
        result = refresh(args.data_root, days=5, workers=args.workers,
                         merge_existing=True)
    elif args.refresh_auto:
        today = datetime.now(timezone.utc).date()
        full = today.weekday() == 6 or not (args.data_root / CACHE).is_file()
        if not full:
            try:
                _existing_for_merge(args.data_root, today)
            except ValueError:
                full = True  # Recover an invalid/incomplete base cache.
        result = refresh(args.data_root, days=WINDOW_DAYS if full else 5,
                         workers=args.workers, merge_existing=not full,
                         resume_archives=full)
    else:
        result = {"status": "READ_ONLY_FORGE_HISTORY_CACHE",
                  "types_ready": len(load(args.data_root)),
                  "station_history_available": False}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
