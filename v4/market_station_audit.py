"""Read-only station-by-station coverage summary for latest recorded V4 run.

Older runs saved structure order counts and filtered market proofs but did
NOT persist every structure's distinct sell type IDs. Do not fabricate them
from raw order count or only qualified market proofs.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from v4.market_depth import STATIONS


def _read(path):
    try:
        o=json.loads(path.read_text(encoding="utf-8"))
        return o if isinstance(o,dict) else {}
    except (OSError,ValueError,UnicodeError):
        return {}


def summarize(root: Path) -> dict:
    base=Path(root)/"runs"
    if not base.is_dir():
        return {"status":"NO_COMPLETED_SCAN"}
    folder=None
    for sub in sorted(base.iterdir(),reverse=True):
        if sub.is_dir() and _read(sub/"manifest.json").get("status")=="SHADOW_RECORDED":
            folder=sub
            break
    if folder is None:
        return {"status":"NO_COMPLETED_SCAN"}
    deep=_read(folder/"deep_shadow.json")
    health=deep.get("structure_health") or {}
    census=deep.get("market_station_sell_census") or {}
    per_station=Counter()
    candidates=Counter()
    try:
        with (folder/"all_proofs.jsonl").open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                row=json.loads(line)
                if row.get("kind")!="market":
                    continue
                src=row.get("source_location")
                for name,ident in STATIONS.items():
                    if src==ident:
                        per_station[name]+=1
                        if row.get("model_candidate") is True:
                            candidates[name]+=1
    except (OSError,ValueError,UnicodeError):
        return {"status":"PROOF_FILE_UNREADABLE","run":folder.name}
    rows={}
    health_names={"4-H":"four_h","C-J":"cj","O4T":"o4t"}
    for name,ident in STATIONS.items():
        lane=health.get(health_names[name]) or {}
        fresh=census.get(name)
        if not isinstance(fresh,dict) or lane.get("status")!="COMPLETE":
            # Failed/partial private-market access must not appear as
            # zero scanned item types or as a complete Jita comparison.
            fresh=None
        rows[name]={
            "structure_id":ident,
            "structure_scan_status":lane.get("status","UNKNOWN"),
            "total_structure_orders":lane.get("orders"),
            "all_active_type_ids":(fresh.get("all_active_type_ids") if fresh else None),
            "active_sell_type_ids":(fresh.get("active_sell_type_ids") if fresh else None),
            "active_sell_orders":(fresh.get("active_sell_orders") if fresh else None),
            "sell_types_with_jita_buy":(fresh.get("sell_types_with_jita_buy") if fresh else None),
            "sell_types_without_jita_buy":(fresh.get("sell_types_without_jita_buy") if fresh else None),
            "sell_types_best_price_crossed":(fresh.get("sell_types_best_price_crossed") if fresh else None),
            "sell_types_optimistic_gate_passed":(fresh.get("sell_types_optimistic_gate_passed") if fresh else None),
            "full_depth_market_pairs_evaluated":per_station[name],
            "market_model_candidates":candidates[name],
            "historical_type_count_complete":fresh is not None,
        }
    return {
        "status":"STATION_COVERAGE_REPORTED",
        "run":folder.name,
        "market_pricing_basis":deep.get("market_pricing_basis"),
        "source_sell_type_count_stored":bool(census),
        "limitations":(
            "OLDER_SCAN_HAS_NO_PERSISTED_DISTINCT_SELL_TYPE_CENSUS"
            if not census else None),
        "stations":rows,
        "verified_live_trade_opportunities":False,
    }


def main():
    parser=argparse.ArgumentParser(description="V4 read-only 4-H/C-J/O4T item coverage")
    parser.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    args=parser.parse_args()
    print(json.dumps(summarize(args.data_root),ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
