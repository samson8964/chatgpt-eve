"""Read-only HY-RWO private-market preflight and gated six-station enrollment.

The exact structure ID comes from the user's EVE in-game showinfo link.
Use the existing Arb Hunter EVE SSO 'dc' profile; no new OAuth scope,
Cloudflare deployment, scan, trade, SQL, or mail operation is performed.
Fail closed on identity mismatch, market errors, partial pagination, or
unrecognized orders. Activation only writes an exact local marker.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import requests

from v4 import structure_registry as registry
from v4.eve_mail_test import WORKER_URL
from v4.hunter_purchase_probe import _dc_character
from v4.local_bridge_auth import get_bridge_key, valid_bridge_key
from v4.structure_transport import all_structure_orders

STATION_LANE, STATION_LABEL, STATION_ID, AUTH_PROFILE = registry.HY_RWO_LANE
STATION_NAME = "HY-RWO - Time Is A Flat Circle (Sensible People)"
EXPECTED_CHARACTER = "Arb Hunter"
EXPECTED_CHARACTER_ID = 2124830062
MAX_PAGES = 2000


def _validate_rows(orders: list) -> bool:
    """Reject mixed-location, duplicated or malformed orders before enrollment."""
    if not isinstance(orders, list) or not orders:
        return False
    ids = set()
    for row in orders:
        if not isinstance(row, dict):
            return False
        sid, oid, typ = (row.get("location_id"), row.get("order_id"),
                         row.get("type_id"))
        if (isinstance(sid, bool) or sid != STATION_ID
                or not isinstance(oid, int) or isinstance(oid, bool)
                or oid <= 0 or oid in ids
                or not isinstance(typ, int) or isinstance(typ, bool)
                or typ <= 0
                or type(row.get("is_buy_order")) is not bool):
            return False
        try:
            price = float(row.get("price"))
            remaining = int(row.get("volume_remain"))
            if (not math.isfinite(price) or price <= 0
                    or remaining < 0 or row.get("volume_remain") != remaining):
                return False
        except (TypeError, ValueError, OverflowError):
            return False
        ids.add(oid)
    return True


def probe(*, full: bool = False, session=None, get_key=None,
          sleep=None, jitter=None) -> dict:
    """Inspect DC login then read only HY-RWO; never touch the other five."""
    result = {
        "station": STATION_NAME, "station_id": STATION_ID,
        "lane": STATION_LANE, "authorization_profile": AUTH_PROFILE,
        "expected_character": EXPECTED_CHARACTER,
        "expected_character_id": EXPECTED_CHARACTER_ID,
        "status": "NOT_TESTED", "enabled": False,
        "orders_saved": False, "email_sent": False,
        "purchases_made": False, "scheduled_scan_started": False,
        "full_market_scan": False,
    }
    try:
        secret = (get_key or get_bridge_key)()
    except Exception:
        return {**result, "status": "LOCAL_CREDENTIAL_UNAVAILABLE"}
    if not valid_bridge_key(secret):
        return {**result, "status": "LOCAL_CREDENTIAL_INVALID"}
    client = session or requests.Session()
    try:
        auth = client.get(WORKER_URL + "/health", timeout=(10, 30))
        if auth.status_code != 200:
            return {**result, "status": "WORKER_HEALTH_NOT_OK",
                    "http_status": int(auth.status_code)}
        name, char_id = _dc_character(auth.text[:30000])
        result.update({"dc_character": name, "dc_character_id": char_id})
        if name != EXPECTED_CHARACTER or char_id != EXPECTED_CHARACTER_ID:
            return {**result, "status": "DC_CHARACTER_MISMATCH"}
    except requests.RequestException:
        return {**result, "status": "WORKER_HEALTH_NETWORK_ERROR"}

    if not full:
        try:
            response = client.get(
                WORKER_URL + "/api/structure-market",
                params={"structure_id": STATION_ID,
                        "auth_profile": AUTH_PROFILE, "page": 1},
                headers={"Authorization": "Bearer " + secret,
                         "User-Agent": "EVE V4 HY-RWO read-only preflight"},
                timeout=(10, 55))
            if response.status_code != 200:
                return {**result, "status": "PAGE1_HTTP_FAILED",
                        "http_status": int(response.status_code)}
            payload = response.json()
            if (not isinstance(payload, dict) or payload.get("ok") is not True
                    or payload.get("structure_id") != STATION_ID
                    or payload.get("page") != 1
                    or type(payload.get("pages")) is not int
                    or not 1 <= payload["pages"] <= MAX_PAGES
                    or not isinstance(payload.get("orders"), list)):
                return {**result, "status": "PAGE1_INVALID_RESPONSE"}
            return {
                **result, "status": "PAGE1_OK",
                "pages_reported": payload["pages"],
                "page1_orders": len(payload["orders"]),
                "full_pagination_verified": False,
            }
        except (requests.RequestException, ValueError, TypeError):
            return {**result, "status": "PAGE1_NETWORK_OR_DATA_ERROR"}

    def fetch(url, *, params, headers, timeout):
        response = client.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json(), response.headers

    kwargs = {}
    if sleep is not None:
        kwargs["sleep"] = sleep
    if jitter is not None:
        kwargs["jitter"] = jitter
    try:
        orders, health = all_structure_orders(
            secret, structures={STATION_LANE: (STATION_ID, AUTH_PROFILE)},
            worker=WORKER_URL, fetch=fetch, **kwargs)
    except Exception:
        return {**result, "status": "FULL_READ_EXCEPTION"}
    lane = health.get(STATION_LANE) or {}
    result["market_health"] = {
        k: lane.get(k) for k in (
            "status", "reason", "http_status", "pages", "pages_fetched",
            "orders", "transient_retries", "failed_page")
        if k in lane
    }
    if (lane.get("status") != "COMPLETE"
            or type(lane.get("pages")) is not int or lane["pages"] < 1
            or lane.get("pages_fetched") != lane["pages"]):
        return {**result, "status": "FULL_READ_INCOMPLETE"}
    if not _validate_rows(orders):
        return {**result, "status": "FULL_READ_ORDER_INTEGRITY_FAILED"}
    return {
        **result, "status": "FULL_PAGES_VERIFIED",
        "orders_count": len(orders),
        "pages_verified": lane["pages"],
        "full_pagination_verified": True,
    }


def activate(result: dict, *, path: Path | None = None) -> dict:
    """Opt in only after full HY book, exact DC identity and existing five mode."""
    if not registry.hunter_enabled():
        raise ValueError("EXISTING_HUNTER_FIVE_MODE_NOT_ENABLED")
    if (result.get("status") != "FULL_PAGES_VERIFIED"
            or result.get("station_id") != STATION_ID
            or result.get("authorization_profile") != AUTH_PROFILE
            or result.get("expected_character") != EXPECTED_CHARACTER
            or result.get("dc_character") != EXPECTED_CHARACTER
            or result.get("dc_character_id") != EXPECTED_CHARACTER_ID
            or result.get("full_pagination_verified") is not True
            or type(result.get("pages_verified")) is not int
            or result["pages_verified"] < 1
            or type(result.get("orders_count")) is not int
            or result["orders_count"] <= 0
            or result.get("orders_saved") is not False
            or result.get("email_sent") is not False):
        raise ValueError("HY_RWO_VERIFICATION_NOT_COMPLETE")
    target = path or registry.HY_RWO_ENABLE_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    try:
        partial.write_text(registry.HY_RWO_ENABLE_CONTENT, encoding="utf-8")
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)
    return {
        "status": "HY_RWO_ENABLED_FOR_NEXT_SCHEDULED_V4_SCAN",
        "station_id": STATION_ID, "station": STATION_NAME,
        "enabled": True, "orders_purchased": 0,
        "email_sent": False, "formal_alerts_changed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true",
                        help="Validate every HY-RWO market page, read-only")
    parser.add_argument("--activate-on-success", action="store_true",
                        help="After a full validated book, stage sixth V4 lane")
    args = parser.parse_args()
    if args.activate_on_success and not args.full:
        parser.error("--activate-on-success requires --full")
    try:
        result = probe(full=args.full)
        if args.activate_on_success:
            result["activation"] = activate(result)
    except (ValueError, OSError) as exc:
        result = {"status": str(exc), "enabled": False,
                  "email_sent": False, "orders_saved": False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in ("PAGE1_OK", "FULL_PAGES_VERIFIED") else 2


if __name__ == "__main__":
    sys.exit(main())
