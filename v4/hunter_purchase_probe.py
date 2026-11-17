"""Opt-in read-only multi-station procurement market preflight for the Hunter character.

The production V4 registry and its existing C-J / O4T / BANESTAR identities
remain unchanged. This diagnostic reuses the Worker 'dc' EVE SSO profile:
a single EVE character with structure-market access can read multiple
Upwell markets. Zero purchases, messages, task changes or database writes.
"""
from __future__ import annotations

import argparse
import os
import html
import json
import re
import sys
import time

import requests

from v4.eve_mail_test import WORKER_URL
from v4.local_bridge_auth import get_bridge_key, valid_bridge_key
from v4 import structure_registry as registry

# Exactly match the single V4 source-of-truth registry. UALX ID and exact
# name were copied from the user's in-game showinfo link on 2026-11-09.
KNOWN = tuple((lane, {
    "banestar": "74L2-U - BANESTAR - BALLS DEEP EDITION",
    "cj": "C-J6MT - 1st Taj Mahgoon",
    "o4t": "O4T-Z5 - Dracarys. Prime",
    "r_arkn": "R-ARKN - BIG MOM",
    "ualx": "UALX-3 - Mothership Bellicose (BC Piggy)",
}[lane], location) for lane, _, location, profile in registry.HUNTER_FIVE_LANES
             if profile == "dc")
MAX_PAGES = 2000


def _dc_character(markup: str) -> tuple[str | None, int | None]:
    """Inspect only the DC identity segment in the public Worker health HTML."""
    segment = re.search(r"DC影子市场授权：.*?</p>", markup, flags=re.DOTALL)
    if not segment:
        return None, None
    visible = html.unescape(re.sub(r"<[^>]+>", "", segment.group(0)))
    match = re.search(r"已授权\s*·\s*(.*?)\s*\((\d+)\)", visible)
    if not match:
        return None, None
    return match.group(1).strip(), int(match.group(2))


def station_catalog() -> list[tuple[str, str, int]]:
    """Every exact structure ID is committed and unique; never infer from system."""
    rows = list(KNOWN)
    if (len(rows) != 5 or len({r[0] for r in rows}) != 5
            or len({r[2] for r in rows}) != 5):
        raise ValueError("FIVE_STRUCTURE_REGISTRY_INVALID")
    return rows


def _fetch_market(session, key: str, station_id: int, page: int):
    response = session.get(
        WORKER_URL + "/api/structure-market",
        params={"structure_id": station_id, "auth_profile": "dc", "page": page},
        headers={"Authorization": "Bearer " + key,
                 "User-Agent": "EVE V4 Hunter market read-only preflight"},
        timeout=(10, 55),
    )
    if response.status_code != 200:
        return response.status_code, None
    try:
        body = response.json()
    except (ValueError, TypeError):
        return 200, None
    if (not isinstance(body, dict) or body.get("ok") is not True or
            body.get("structure_id") != station_id or body.get("page") != page or
            not isinstance(body.get("orders"), list)):
        return 200, None
    return 200, body


def probe(*, expected_name: str, full: bool = False,
          session=None, get_key=None, sleep=time.sleep) -> dict:
    stations = station_catalog()
    result = {
        "mode": "READ_ONLY_PROCUREMENT_SCOUT", "expected_character": expected_name,
        "auth_profile": "dc", "stations": {}, "sent": False, "orders_saved": False,
        "purchase_enabled": False, "production_registry_changed": False,
    }
    if not expected_name or not expected_name.strip():
        return {**result, "status": "CHARACTER_NAME_REQUIRED"}
    key_fn = get_key or get_bridge_key
    try:
        key = key_fn()
    except Exception:
        return {**result, "status": "LOCAL_CREDENTIAL_UNAVAILABLE"}
    if not valid_bridge_key(key):
        return {**result, "status": "LOCAL_CREDENTIAL_MISSING_OR_INVALID"}
    client = session or requests.Session()
    try:
        health = client.get(WORKER_URL + "/health", timeout=(10, 30))
        if health.status_code != 200:
            return {**result, "status": "WORKER_STATUS_UNAVAILABLE"}
        actual, character_id = _dc_character(health.text[:30000])
        result["authorized_character"] = actual
        result["authorized_character_id"] = character_id
        if actual != expected_name:
            return {**result, "status": "DC_CHARACTER_MISMATCH_OR_NOT_AUTHORIZED"}
    except requests.RequestException:
        return {**result, "status": "WORKER_STATUS_NETWORK_ERROR"}

    any_failure = False
    for lane, name, station_id in stations:
        record = {"name": name, "structure_id": station_id}
        try:
            status, first = _fetch_market(client, key, station_id, 1)
            if status != 200 or first is None:
                record.update({"status": "HTTP_FAILURE" if status != 200
                               else "INVALID_RESPONSE", "http_status": status})
                any_failure = True
            else:
                pages = first.get("pages")
                if not isinstance(pages, int) or not 1 <= pages <= MAX_PAGES:
                    record["status"] = "INVALID_PAGE_COUNT"
                    any_failure = True
                else:
                    record.update({
                        "status": "PAGE1_OK", "pages_reported": pages,
                        "page1_orders": len(first["orders"]), "pages_fetched": 1,
                        "full_pagination_verified": False,
                    })
                    if full:
                        count = len(first["orders"])
                        for page in range(2, pages + 1):
                            sleep(0.25)
                            code, body = _fetch_market(client, key, station_id, page)
                            if code != 200 or body is None or body.get("pages") != pages:
                                record.update({
                                    "status": "FULL_PAGINATION_FAILED",
                                    "http_status": code, "failed_page": page,
                                })
                                any_failure = True
                                break
                            count += len(body["orders"])
                            record["pages_fetched"] = page
                        else:
                            record.update({
                                "status": "COMPLETE", "orders_count": count,
                                "full_pagination_verified": True,
                            })
        except requests.RequestException:
            record["status"] = "NETWORK_ERROR"
            any_failure = True
        result["stations"][lane] = record
    result["status"] = "ACCESS_FAILED" if any_failure else (
        "FULL_PAGES_COMPLETE" if full else "FIVE_FIRST_PAGES_OK"
    )
    return result


def activate_verified_hunter_mode(result: dict, *, path=None) -> dict:
    """Atomic opt-in, only after five fully paginated ESI structure books."""
    expected = {lane: sid for lane, _, sid, profile in registry.HUNTER_FIVE_LANES
                if profile == "dc"}
    actual = result.get("stations") or {}
    if (result.get("status") != "FULL_PAGES_COMPLETE"
            or result.get("expected_character") != "Arb Hunter"
            or result.get("authorized_character") != "Arb Hunter"
            or not isinstance(result.get("authorized_character_id"), int)
            or result["authorized_character_id"] <= 0
            or set(actual) != set(expected)
            or any(actual[lane].get("structure_id") != sid
                   or actual[lane].get("status") != "COMPLETE"
                   or actual[lane].get("full_pagination_verified") is not True
                   or actual[lane].get("pages_fetched") != actual[lane].get("pages_reported")
                   for lane, sid in expected.items())):
        raise ValueError("HUNTER_FIVE_STATION_VERIFICATION_NOT_COMPLETE")
    dest = path or registry.HUNTER_ENABLE_FILE
    dest.parent.mkdir(parents=True, exist_ok=True)
    staged = dest.with_suffix(dest.suffix + ".part")
    try:
        staged.write_text(registry.HUNTER_ENABLE_CONTENT, encoding="utf-8")
        os.replace(staged, dest)
    finally:
        staged.unlink(missing_ok=True)
    return {"status": "HUNTER_FIVE_STATIONS_ENABLED_FOR_NEXT_V4_RUN",
            "active_market_lanes": list(expected),
            "character": "Arb Hunter",
            "orders_purchased": 0, "emails_sent": 0,
            "formal_opportunity_push_changed": False,
            "enabled": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-name", default="Arb Hunter")
    parser.add_argument("--full", action="store_true",
                        help="Read all market pages from all five; no order persistence")
    parser.add_argument("--activate-on-success", action="store_true",
                        help="Requires --full; enable existing V4 research scanner only after all five pass")
    opts = parser.parse_args()
    if opts.activate_on_success and not opts.full:
        parser.error("--activate-on-success requires --full")
    try:
        summary = probe(expected_name=opts.expected_name, full=opts.full)
        if opts.activate_on_success:
            activation = activate_verified_hunter_mode(summary)
            summary["activation"] = activation
    except ValueError as exc:
        summary = {"status": str(exc), "orders_saved": False,
                   "purchase_enabled": False, "activation": {"enabled": False}}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] in (
        "FIVE_FIRST_PAGES_OK", "FULL_PAGES_COMPLETE"
    ) else 2


if __name__ == "__main__":
    sys.exit(main())
