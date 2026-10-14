"""One-page, read-only access check for all three EVE player structures.

Does not fetch the full market, write SQL, log any key, or send email.
A passing first-page test does not establish that all pages will work.
"""
from __future__ import annotations

import json
from typing import Callable

from v4.deep_scan import STRUCTURES, WORKER
from v4.local_run import deep_scan_environment


def probe(*, fetch: Callable | None = None, env: dict[str, str] | None = None) -> dict:
    if fetch is None:
        import requests
        fetch = requests.get
    if env is None:
        env = deep_scan_environment()
    key = env.get("EVE_MARKET_API_KEY")
    if not key:
        return {"credential_present": False, "probe_result": "MISSING_KEY",
                "mail_enabled": False,
                "structures": {name: {"status": "NOT_TESTED_MISSING_KEY"} for name in STRUCTURES}}
    results = {}
    for name, (structure_id, profile) in STRUCTURES.items():
        try:
            res = fetch(WORKER + "/api/structure-market",
                        params={"structure_id":structure_id,
                                "auth_profile":profile,"page":1},
                        headers={"Authorization": "Bearer " + key}, timeout=(10, 45))
            if res.status_code in (401, 403):
                results[name] = {"status": "ACCESS_DENIED", "http_status": res.status_code}
                continue
            if res.status_code != 200:
                results[name] = {"status": "HTTP_FAILURE", "http_status": res.status_code}
                continue
            body = res.json()
            if not body.get("ok") or int(body.get("structure_id", 0)) != structure_id:
                results[name] = {"status": "INVALID_BRIDGE_RESPONSE"}
                continue
            results[name] = {"status": "PAGE1_OK", "pages_reported": int(body.get("pages") or 1),
                             "page1_order_count": len(body.get("orders") or [])}
        except Exception as exc:
            results[name] = {"status": "REQUEST_FAILED", "error_type": type(exc).__name__}
    return {"credential_present":True,"probe_result":"PAGE1_ONLY",
            "structures":results,"mail_enabled":False, "full_pagination_verified":False}


def main():
    print(json.dumps(probe(),indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
