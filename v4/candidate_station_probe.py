"""Read-only FIRST-PAGE access preflight for the proposed 74L2-U S0B structure.

Tests only the three already-authorized Worker profiles, without downloading
market orders, persisting responses, changing the V4 approved source list, or
sending notifications. Never print credentials, error bodies, HTTP headers or
private order data. Not a production enrollment.
"""
from __future__ import annotations

import json
import sys

import requests

from v4.deep_scan import WORKER, UA
from v4.local_bridge_auth import get_bridge_key, valid_bridge_key

STATION_NAME = "74L2-U - BANESTAR - BALLS DEEP EDITION (S0B Holdings)"
STATION_ID = 1050474463169
PROFILES = ("main", "cj", "dc")


def _safe_status(code: int) -> str:
    if code == 200:
        return "FIRST_PAGE_ACCESS_OK"
    if code == 403:
        return "NO_MARKET_ACCESS_FOR_CHARACTER"
    if code == 401:
        return "AUTHENTICATION_FAILED"
    if code == 502:
        return "UPSTREAM_ESI_ERROR_CHECK_SSO_OR_STRUCTURE"
    if code == 429:
        return "RATE_LIMITED"
    if code in (404, 405):
        return "WORKER_ROUTE_FAILURE"
    if 500 <= code <= 599:
        return "WORKER_OR_UPSTREAM_FAILURE"
    return "OTHER_HTTP_STATUS"


def probe(*, key=None, get=None) -> dict:
    """Run three bounded, streaming GETs. Never consume success/error bodies."""
    secret = get_bridge_key() if key is None else key
    if not valid_bridge_key(secret):
        return {
            "status": "BRIDGE_CREDENTIAL_MISSING_OR_INVALID",
            "station_id": STATION_ID,
            "enrolled": False,
            "orders_saved": False,
            "secret_displayed": False,
        }

    fetch = get or requests.get
    results = {}
    for profile in PROFILES:
        try:
            with fetch(
                WORKER + "/api/structure-market",
                params={"structure_id": STATION_ID, "auth_profile": profile, "page": 1},
                headers={"Authorization": "Bearer " + secret, "User-Agent": UA},
                timeout=(10, 25),
                stream=True,
            ) as response:
                code = response.status_code
                results[profile] = {
                    "http_status": code,
                    "access_result": _safe_status(code),
                }
        except requests.Timeout:
            results[profile] = {"access_result": "TIMEOUT"}
        except requests.ConnectionError:
            results[profile] = {"access_result": "CONNECTION_FAILURE"}
        except requests.RequestException:
            results[profile] = {"access_result": "OTHER_REQUEST_ERROR"}
    return {
        "status": "CANDIDATE_ACCESS_PROBED_NOT_ENROLLED",
        "station": STATION_NAME,
        "station_id": STATION_ID,
        "profiles": results,
        "enrolled": False,
        "orders_saved": False,
        "secret_displayed": False,
        "production_push_unchanged": True,
    }


def main() -> int:
    try:
        result = probe()
    except Exception:
        result = {"status": "LOCAL_PROBE_ERROR", "secret_displayed": False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "CANDIDATE_ACCESS_PROBED_NOT_ENROLLED" else 2


if __name__ == "__main__":
    sys.exit(main())
