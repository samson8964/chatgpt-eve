"""Opt-in read-only multi-station procurement market preflight for the Hunter character.

The production V4 registry and its existing C-J / O4T / BANESTAR identities
remain unchanged. This diagnostic reuses the Worker 'dc' EVE SSO profile:
a single EVE character with structure-market access can read multiple
Upwell markets. Zero purchases, messages, task changes or database writes.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time

import requests

from v4.eve_mail_test import WORKER_URL
from v4.local_bridge_auth import get_bridge_key, valid_bridge_key

# IDs from the existing V4 registry except R-ARKN, externally cross-checked
# on EveSynapse. That ID must still be verified against authenticated ESI.
KNOWN = (
    ("banestar", "74L2-U - BANESTAR - BALLS DEEP EDITION", 1050474463169),
    ("cj", "C-J6MT - 1st Taj Mahgoon", 1049588174021),
    ("o4t", "O4T-Z5 - Dracarys. Prime", 1040804972352),
    ("r_arkn", "R-ARKN - BIG MOM", 1048663825563),
)
UALX_NAME = "UALX-3 - Mothership Bellicose"
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


def station_catalog(ualx_id: int | None = None) -> list[tuple[str, str, int | None]]:
    if ualx_id is not None and (isinstance(ualx_id, bool) or
                                not isinstance(ualx_id, int) or
                                not 10**12 <= ualx_id <= 9*10**15 or
                                ualx_id in {r[2] for r in KNOWN}):
        raise ValueError("UALX_STRUCTURE_ID_INVALID")
    return list(KNOWN) + [("ualx", UALX_NAME, ualx_id)]


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


def probe(*, expected_name: str, ualx_id: int | None = None,
          full: bool = False, session=None, get_key=None, sleep=time.sleep) -> dict:
    stations = station_catalog(ualx_id)
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
        if station_id is None:
            result["stations"][lane] = {
                "name": name, "status": "NEEDS_EXACT_STRUCTURE_ID",
                "source": "IN_GAME_SHOWINFO_LINK_REQUIRED",
            }
            continue
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
        "PENDING_UALX_ID" if ualx_id is None else
        "FULL_PAGES_COMPLETE" if full else "FIVE_FIRST_PAGES_OK"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-name", default="Arb Hunter")
    parser.add_argument("--ualx-id", type=int, default=None,
                        help="Exact player structure ID, copied from EVE showinfo link")
    parser.add_argument("--full", action="store_true",
                        help="Read all pages for each structure, with no persistence")
    opts = parser.parse_args()
    try:
        summary = probe(expected_name=opts.expected_name,
                        ualx_id=opts.ualx_id, full=opts.full)
    except ValueError as exc:
        summary = {"status": str(exc), "orders_saved": False,
                   "purchase_enabled": False}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] in (
        "PENDING_UALX_ID", "FIVE_FIRST_PAGES_OK", "FULL_PAGES_COMPLETE"
    ) else 2


if __name__ == "__main__":
    sys.exit(main())
