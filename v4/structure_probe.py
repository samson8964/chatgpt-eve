"""Minimal read-only Worker health probe for three authorized structure profiles.

Makes ONE page-1 request per approved structure. Does not download or
persist orders, secrets, response bodies, or HTTP request headers.
Designed for troubleshooting NONRETRYABLE_REQUEST without a full scan.
"""
from __future__ import annotations

import json
import sys

import requests

from v4.deep_scan import STRUCTURES, WORKER, UA
from v4.local_bridge_auth import get_bridge_key, valid_bridge_key


def probe(*, key=None, get=None) -> dict:
    key = get_bridge_key() if key is None else key
    if not valid_bridge_key(key):
        return {"status": "BRIDGE_CREDENTIAL_MISSING_OR_INVALID",
                "profiles": {}}
    fetch = get or requests.get
    rows = {}
    for name, (structure_id, profile) in STRUCTURES.items():
        # No credentials in URL, diagnostic JSON, or exception text.
        try:
            with fetch(
                WORKER + "/api/structure-market",
                params={"structure_id": structure_id, "auth_profile": profile,
                        "page": 1},
                headers={"Authorization": "Bearer " + key, "User-Agent": UA},
                timeout=(10, 25),
                stream=True,
            ) as response:
                code = response.status_code
                rows[name] = {"http_status": code,
                              "category": (
                                  "OK" if code == 200 else
                                  "AUTH_OR_ACCESS_DENIED" if code in (401, 403) else
                                  "ROUTE_NOT_FOUND" if code in (404, 405) else
                                  "RATE_LIMITED" if code == 429 else
                                  "UPSTREAM_OR_WORKER_FAILURE" if 500 <= code <= 599 else
                                  "OTHER_HTTP_ERROR")}
        except requests.Timeout:
            rows[name] = {"category": "TIMEOUT"}
        except requests.ConnectionError:
            rows[name] = {"category": "CONNECTION_FAILURE"}
        except requests.RequestException:
            rows[name] = {"category": "OTHER_REQUEST_ERROR"}
    return {"status": "PROBED_THREE_FIRST_PAGES_NO_ORDERS_STORED",
            "profiles": rows,
            "secret_displayed": False,
            "orders_saved": False}


def main() -> int:
    try:
        result = probe()
    except Exception:
        # Unexpected local Credential Manager errors must never print a
        # traceback containing a credential, URL or untrusted response.
        result = {"status": "LOCAL_PROBE_ERROR", "secret_displayed": False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PROBED_THREE_FIRST_PAGES_NO_ORDERS_STORED" else 2


if __name__ == "__main__":
    sys.exit(main())
