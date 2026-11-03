"""Standalone read-only full pagination audit of all 3 EVE player structures.

Uses the same retrying transport as V4 deep_scan. Never downloads public
market contracts, never writes SQL, and never sends mail.
"""
from __future__ import annotations

import json

from v4.local_run import deep_scan_environment


def diagnose() -> dict:
    from v4.deep_scan import all_structure_orders
    token=deep_scan_environment().get("EVE_MARKET_API_KEY", "")
    if not token:
        return {"status":"MISSING_LOCAL_CREDENTIAL","structures":{},
                "mail_enabled":False,"full_market_scan":False}
    orders, health=all_structure_orders(token)
    complete=len(health)==3 and all(h.get("status")=="COMPLETE" for h in health.values())
    return {"status":"ALL_STRUCTURE_PAGES_COMPLETE" if complete else "PARTIAL_STRUCTURE_READ",
            "structures": {key: {field: val for field,val in row.items()
                                 if field in ("status","reason","pages","pages_fetched",
                                              "failed_page","attempts_on_failed_page",
                                              "orders","transient_retries")}
                           for key,row in health.items()},
            "structure_order_count":len(orders),
            "mail_enabled":False,
            "full_market_scan":False,
            "sql_written":False}


def main():
    result=diagnose()
    print(json.dumps(result,indent=2,ensure_ascii=False))
    if result["status"] != "ALL_STRUCTURE_PAGES_COMPLETE":
        raise SystemExit(2)


if __name__=="__main__":
    main()
