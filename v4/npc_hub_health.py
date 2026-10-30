"""NPC trade-hub visibility for V4 public market snapshot diagnostics.

Presence in a public snapshot is NOT independent ESI pagination verification.
Jita is the single destination BUY-depth benchmark, while Amarr/Dodixie are
approved alternative source sell locations. No scanning or policy changes.
"""
from __future__ import annotations

import argparse
import bz2
import csv
import json
from pathlib import Path
from typing import Iterable

HUBS = {
    "jita": ("吉他4-4 / Jita IV-4", 60003760, "BUY_DEPTH_VALUATION_BENCHMARK"),
    "amarr": ("艾玛VIII / Amarr VIII", 60008494, "APPROVED_SOURCE_MARKET"),
    "dodixie": ("多迪谢IX / Dodixie IX", 60011866, "APPROVED_SOURCE_MARKET"),
}
BY_ID = {station: key for key, (_, station, _) in HUBS.items()}
BASIS = "PUBLIC_MARKET_SNAPSHOT_NOT_LIVE_ESI_PAGINATION_VERIFIED"


def _blank() -> dict:
    return {
        key: {
            "station_name": label,
            "station_id": station,
            "role": role,
            "status": "NO_ACTIVE_ORDERS_IN_PUBLIC_SNAPSHOT",
            "active_orders": 0,
            "active_buy_orders": 0,
            "active_sell_orders": 0,
            "active_buy_type_ids": 0,
            "active_sell_type_ids": 0,
            "evidence": BASIS,
            "station_page_coverage": "NOT_PROVIDED_BY_PUBLIC_SNAPSHOT",
        }
        for key, (label, station, role) in HUBS.items()
    }


def _summarize(pairs: Iterable[tuple[int, int, bool]]) -> dict:
    result = _blank()
    types: dict[str, tuple[set[int], set[int]]] = {
        key: (set(), set()) for key in HUBS
    }
    for location, type_id, buy in pairs:
        key = BY_ID.get(location)
        if key is None:
            continue
        row = result[key]
        row["active_orders"] += 1
        if buy:
            row["active_buy_orders"] += 1
            types[key][0].add(type_id)
        else:
            row["active_sell_orders"] += 1
            types[key][1].add(type_id)
    for key, row in result.items():
        row["active_buy_type_ids"] = len(types[key][0])
        row["active_sell_type_ids"] = len(types[key][1])
        if row["active_buy_orders"] and row["active_sell_orders"]:
            row["status"] = "BOTH_SIDES_PRESENT_IN_PUBLIC_SNAPSHOT"
        elif row["active_orders"]:
            row["status"] = "ONE_SIDE_ONLY_IN_PUBLIC_SNAPSHOT"
    return result


def from_orders(orders: Iterable) -> dict:
    """Accept the ALREADY validated public orders from deep_scan."""
    return _summarize(
        (int(o.location_id), int(o.type_id), bool(o.buy)) for o in orders
    )


def inspect_csv(path: Path) -> dict:
    """Read an existing public CSV.bz2 without mutating scanner state."""
    path = Path(path)
    if path.suffix != ".bz2" or not path.is_file() or path.is_symlink():
        raise ValueError("NPC_HUB_PUBLIC_MARKET_ARCHIVE_INVALID")
    rows = []
    # Do not store 1.6m rows; only aggregate the three known station IDs.
    counts = _blank()
    types = {key: (set(), set()) for key in HUBS}
    with bz2.open(path, "rt", newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        mandatory = {"location_id", "type_id", "price",
                     "volume_remain", "is_buy_order"}
        if not mandatory.issubset(reader.fieldnames or []):
            raise ValueError("NPC_HUB_MARKET_CSV_COLUMNS_MISSING")
        for row in reader:
            try:
                key = BY_ID.get(int(row["location_id"]))
                if key is None:
                    continue
                typ = int(row["type_id"])
                price = float(row["price"])
                volume = int(float(row["volume_remain"]))
                buy = str(row["is_buy_order"]).lower() in ("true", "t", "1")
                if typ <= 0 or price <= 0 or volume <= 0:
                    continue
            except (ValueError, TypeError, OverflowError):
                continue
            item = counts[key]
            item["active_orders"] += 1
            if buy:
                item["active_buy_orders"] += 1
                types[key][0].add(typ)
            else:
                item["active_sell_orders"] += 1
                types[key][1].add(typ)
    for key, item in counts.items():
        item["active_buy_type_ids"] = len(types[key][0])
        item["active_sell_type_ids"] = len(types[key][1])
        if item["active_buy_orders"] and item["active_sell_orders"]:
            item["status"] = "BOTH_SIDES_PRESENT_IN_PUBLIC_SNAPSHOT"
        elif item["active_orders"]:
            item["status"] = "ONE_SIDE_ONLY_IN_PUBLIC_SNAPSHOT"
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only health counts for Jita, Amarr, Dodixie public markets")
    parser.add_argument("--market", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({
        "status": "READ_ONLY_PUBLIC_NPC_HUB_SNAPSHOT_INSPECTION",
        "mutated": False,
        "npc_trade_hub_health": inspect_csv(args.market),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
