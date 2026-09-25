from __future__ import annotations

import json
import os
import time
from pathlib import Path

from scanner_source import (
    DATA,
    MARKET_ORDERS_INDEX,
    PUBLIC_CONTRACTS_INDEX,
    download,
    latest_file,
    load_contracts,
    load_market_orders,
)
import four_h_contract_scanner as four_h

REPORT = Path("results/latest/v31_prefetch.json")


def _ensure(index_url: str) -> tuple[Path, str]:
    url, modified = latest_file(index_url)
    path = DATA / Path(url).name
    if not path.exists():
        download(url, path)
    return path, modified


def main() -> None:
    started = time.perf_counter()

    contracts_path, contracts_modified = _ensure(PUBLIC_CONTRACTS_INDEX)
    market_path, market_modified = _ensure(MARKET_ORDERS_INDEX)

    t0 = time.perf_counter()
    contracts, items = load_contracts(contracts_path)
    contracts_parse_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    market = load_market_orders(market_path)
    market_parse_s = time.perf_counter() - t0

    # Populate the run-scoped shared 4-H cache once. All three 4-H scanners in
    # V3.1 consume this exact snapshot, eliminating duplicate pagination calls.
    t0 = time.perf_counter()
    structure_orders = four_h.fetch_structure_orders()
    structure_fetch_s = time.perf_counter() - t0

    payload = {
        "engine_version": "Opportunity Engine V3.1",
        "contracts_file": contracts_path.name,
        "contracts_modified": contracts_modified,
        "contracts_rows": int(len(contracts)),
        "contract_items_rows": int(len(items)),
        "market_file": market_path.name,
        "market_modified": market_modified,
        "market_rows": int(len(market)),
        "structure_orders": int(len(structure_orders)),
        "contracts_parse_seconds": round(contracts_parse_s, 3),
        "market_parse_seconds": round(market_parse_s, 3),
        "structure_fetch_seconds": round(structure_fetch_s, 3),
        "total_seconds": round(time.perf_counter() - started, 3),
        "parsed_cache_dir": os.getenv("V31_PARSED_CACHE_DIR", ""),
        "structure_cache": os.getenv("V31_STRUCTURE_ORDERS_CACHE", ""),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
