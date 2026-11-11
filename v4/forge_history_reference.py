"""Official ESI *regional daily trade history* reference, never a Jita fill.

EVE ESI has no per-station trade tape or exact last executed trade price.
The latest completed day with traded volume in The Forge (10000002) supplies
an explicitly labelled DAY-AVERAGE historical *research* quote. This must
never be called a Jita 4-4 execution price or a live sellable bid.

An explicit one-off refresh downloads EVE Ref's daily archives of the
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


def refresh(root: Path, *, days: int = WINDOW_DAYS, today: date | None = None,
            fetch=None, workers: int = 4) -> dict:
    """Explicit slow data preparation; NEVER invoked from shadow scanning.

    Retrieve completed days only. If current publisher snapshots are missing,
    keep the old cache untouched and return an error (no fabricated quote).
    """
    if not 1 <= days <= WINDOW_DAYS or not 1 <= workers <= 6:
        raise ValueError("HISTORY_REFRESH_BOUNDS_INVALID")
    today = today or datetime.now(timezone.utc).date()
    def download(day):
        url = ("https://data.everef.net/market-history/"
               + str(day.year) + "/market-history-" + day.isoformat()
               + ".csv.bz2")
        if fetch:
            blob = fetch(url)
        else:
            response = requests.get(
                url, timeout=(15, 50), headers={"User-Agent":
                "V4 EVE history research / github.com/samson8964/chatgpt-eve"})
            if response.status_code == 404:
                return day, None
            response.raise_for_status()
            blob = response.content
        return day, _parse_day(blob, day)
    days_to_fetch = [today - timedelta(days=n) for n in range(1, days + 1)]
    fetched = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(download, day): day for day in days_to_fetch}
        for task in as_completed(jobs):
            day, records = task.result()
            if records is not None:
                fetched[day] = records
    recent = [d for d in fetched if (today-d).days <= 3]
    if not recent or not any(fetched[d] for d in recent):
        raise ValueError("FORGE_HISTORY_RECENT_PUBLISHER_MISSING")
    if len(fetched) < min(days, 5):
        raise ValueError("FORGE_HISTORY_ARCHIVE_COVERAGE_INCOMPLETE")
    quotes = {}
    for day in sorted(fetched):
        for typ, info in fetched[day].items():
            quotes[str(typ)] = info  # Newest day with volume supersedes.
    if not quotes:
        raise ValueError("FORGE_HISTORY_NO_REPORTED_TRADES")
    path = Path(root) / CACHE
    path.parent.mkdir(parents=True, exist_ok=True)
    result = {"schema": 1, "region_id": FORGE_REGION_ID,
              "source": SOURCE, "built_on": today.isoformat(),
              "window_days": days, "days_available": len(fetched),
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
            "cache": str(path)}


def main():
    from argparse import ArgumentParser
    p = ArgumentParser(description="Explicit 90-day regional trade-history cache")
    p.add_argument("--data-root", type=Path,
                   default=Path.home()/"EVE-V4-Data")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--days", type=int, default=WINDOW_DAYS)
    args = p.parse_args()
    if args.refresh:
        result = refresh(args.data_root, days=args.days)
    else:
        result = {"status": "READ_ONLY_FORGE_HISTORY_CACHE",
                  "types_ready": len(load(args.data_root)),
                  "station_history_available": False}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
