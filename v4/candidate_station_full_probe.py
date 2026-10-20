"""Private market full-pagination canary for 74L2-U, NOT a scheduled scan.

Reads the new station with the existing DC profile through the unchanged
Worker bridge. All order rows remain in memory; only fixed-category integrity
and aggregate counts are displayed. Does not enroll a station, send mail,
touch old 4-H/C-J/O4T market data, or change any scheduled task.
"""
from __future__ import annotations

import json
import sys

from v4.candidate_station_probe import STATION_ID
from v4.deep_scan import WORKER, request
from v4.local_bridge_auth import get_bridge_key, valid_bridge_key
from v4.structure_transport import all_structure_orders

STATION = "74L2-U"
AUTH_PROFILE = "dc"


def probe(*, key=None, fetch=request, sleep=None, jitter=None) -> dict:
    """Reuse the exact production pagination verifier for just this location."""
    secret = get_bridge_key() if key is None else key
    result = {
        "status": "NOT_TESTED",
        "station": STATION,
        "station_id": STATION_ID,
        "authorization_profile": AUTH_PROFILE,
        "enrolled": False,
        "orders_saved": False,
        "secret_displayed": False,
        "emails_sent": False,
    }
    if not valid_bridge_key(secret):
        return {**result, "status": "BRIDGE_CREDENTIAL_MISSING_OR_INVALID"}
    kwargs = {}
    if sleep is not None:
        kwargs["sleep"] = sleep
    if jitter is not None:
        kwargs["jitter"] = jitter
    try:
        rows, health = all_structure_orders(
            secret,
            structures={"banestar": (STATION_ID, AUTH_PROFILE)},
            worker=WORKER,
            fetch=fetch,
            **kwargs,
        )
        lane = health["banestar"]
        diagnostic = {name: lane.get(name) for name in (
            "status", "reason", "http_status", "pages", "pages_fetched",
            "orders", "failed_page", "transient_retries",
        ) if name in lane}
        result["market_health"] = diagnostic
        if lane.get("status") != "COMPLETE":
            return {**result, "status": "FULL_BOOK_COLLECTION_FAILED"}
        if not rows:
            return {**result, "status": "COMPLETE_EMPTY_BOOK"}
        identifiers = set()
        sell_types = set()
        buys = sells = 0
        try:
            for entry in rows:
                if not isinstance(entry, dict):
                    raise ValueError("bad row")
                if int(entry["location_id"]) != STATION_ID:
                    raise ValueError("wrong location")
                order_id = int(entry["order_id"])
                type_id = int(entry["type_id"])
                if order_id <= 0 or type_id <= 0 or order_id in identifiers:
                    raise ValueError("duplicate or invalid order")
                identifiers.add(order_id)
                side = entry["is_buy_order"]
                if not isinstance(side, bool):
                    raise ValueError("invalid side")
                if side:
                    buys += 1
                else:
                    sells += 1
                    sell_types.add(type_id)
        except (ValueError, TypeError, KeyError, OverflowError):
            return {**result, "status": "FULL_BOOK_ROW_INTEGRITY_FAILED"}
        result.update({
            "status": "FULL_BOOK_VALIDATED_NOT_ENROLLED",
            "active_buy_orders": buys,
            "active_sell_orders": sells,
            "distinct_sell_type_ids": len(sell_types),
        })
        return result
    except Exception:
        # Never log untrusted request exception details or authorization values.
        return {**result, "status": "FULL_BOOK_PROBE_EXCEPTION"}


def main() -> int:
    result = probe()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "FULL_BOOK_VALIDATED_NOT_ENROLLED" else 2


if __name__ == "__main__":
    sys.exit(main())
