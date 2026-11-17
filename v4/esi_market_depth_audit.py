"""Offline forensic ESI versus EVE Ref market-depth audit, never live signals.

Uses existing one-shot ESI verification comparison.sqlite3, READ-ONLY.
Only writes a separate JSON into its same isolated validation run folder.
This is not a V4 profit/model-candidate audit: original comparison schemas
omit essential min_volume and range order execution fields.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path

JITA = 60003760
RUN_NAME = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")
ANOMALY_REGIONS = (10000030,10000027,10000014,10000066,11000004,10000010)


class OfflineAuditError(RuntimeError):
    pass


def _one(con,sql,params=()):
    return con.execute(sql,params).fetchone()[0]


def _unmatched_by_region(con,table,other):
    """One unmatched-order pass per source, not repeated 24x full scans.

    Order-id primary-key lookup is efficient; region is not indexed in the
    original independent comparison DB and must not be altered here.
    """
    groups=defaultdict(list)
    for region,location,buy,count,types in con.execute(f"""
        SELECT a.region_id,a.location_id,a.is_buy_order,
               COUNT(*) AS n,COUNT(DISTINCT a.type_id) AS types
        FROM {table} a
        WHERE NOT EXISTS
          (SELECT 1 FROM {other} b WHERE b.order_id=a.order_id)
        GROUP BY a.region_id,a.location_id,a.is_buy_order
    """):
        groups[region].append({
            "location_id":int(location),"buy":bool(buy),
            "count":int(count),"distinct_types":int(types)})
    return groups


def _location_deltas(region_id,esi_unmatched,ref_unmatched,limit=8):
    def top(groups):
        rows=groups.get(region_id,[])
        return sorted(rows,key=lambda x:(-x["count"],x["location_id"]))[:limit]
    return {
        "region_id":region_id,
        "everef_only_locations":top(ref_unmatched),
        "esi_only_locations":top(esi_unmatched),
        "everef_only_total":sum(
            x["count"] for x in ref_unmatched.get(region_id,[])),
        "esi_only_total":sum(
            x["count"] for x in esi_unmatched.get(region_id,[])),
    }


def _book(con,table,location=JITA):
    """Map of BUY type to price levels, with positive outstanding depth."""
    result=defaultdict(list)
    for typ,price,amount,order_count in con.execute(f"""
        SELECT type_id,price,SUM(volume_remain),COUNT(*)
        FROM {table} WHERE location_id=? AND is_buy_order=1
          AND price>0 AND volume_remain>0
        GROUP BY type_id,price
        ORDER BY type_id,price DESC
    """,(location,)):
        result[int(typ)].append((float(price),int(amount),int(order_count)))
    return result


def _top_five(levels):
    window=levels[:5]
    return {
        "best_bid_isk":window[0][0] if window else None,
        "five_distinct_price_levels":len(window),
        "five_level_quantity":sum(x[1] for x in window),
        "five_level_order_count":sum(x[2] for x in window),
        "five_level_notional_isk":round(sum(x[0]*x[1] for x in window),2),
    }


def _depth_audit(esi,ref,limit=25):
    """Compare best quotes and depth, NOT execution-validated fills."""
    same=sorted(set(esi)&set(ref))
    only_esi=sorted(set(esi)-set(ref))
    only_ref=sorted(set(ref)-set(esi))
    best_changed=[]
    depth_changed=0
    totals={"esi_five_level_qty":0,"everef_five_level_qty":0}
    for typ in same:
        lhs=_top_five(esi[typ]);rhs=_top_five(ref[typ])
        totals["esi_five_level_qty"]+=lhs["five_level_quantity"]
        totals["everef_five_level_qty"]+=rhs["five_level_quantity"]
        if lhs["five_level_quantity"]!=rhs["five_level_quantity"]:
            depth_changed+=1
        if lhs["best_bid_isk"]!=rhs["best_bid_isk"]:
            diff=lhs["best_bid_isk"]-rhs["best_bid_isk"]
            pct=(diff/rhs["best_bid_isk"]*100
                 if rhs["best_bid_isk"] else None)
            best_changed.append({
                "type_id":typ,
                "esi_best_bid":lhs["best_bid_isk"],
                "everef_best_bid":rhs["best_bid_isk"],
                "price_change_pct":round(pct,3) if pct is not None else None,
                "esi_five_level_qty":lhs["five_level_quantity"],
                "everef_five_level_qty":rhs["five_level_quantity"],
                "esi_five_level_notional":lhs["five_level_notional_isk"],
                "everef_five_level_notional":rhs["five_level_notional_isk"],
            })
    # Prioritize large relative changes, not item IDs or arbitrary price scales.
    best_changed.sort(key=lambda x:(
        -abs(x["price_change_pct"] or 0),x["type_id"]))
    return {
        "location_id":JITA,
        "both_sources_with_buy_orders":len(same),
        "only_esi_type_count":len(only_esi),
        "only_everef_type_count":len(only_ref),
        "only_esi_type_samples":only_esi[:limit],
        "only_everef_type_samples":only_ref[:limit],
        "best_bid_changed_type_count":len(best_changed),
        "five_price_level_quantity_changed_type_count":depth_changed,
        "five_level_quantity_totals_matched_types_only":totals,
        "top_best_bid_change_types":best_changed[:limit],
        "warning":"Prices and top five levels are snapshot research. This database lacks ESI order min_volume, range and haul/fees; these values CANNOT establish executable arbitrage or V4 net-profit candidates.",
    }


def audit(root:Path,run_id:str):
    if not RUN_NAME.fullmatch(run_id):
        raise OfflineAuditError("INVALID_ESI_RUN_NAME")
    folder=Path(root)/"esi-parallel-validation"/run_id
    report_file=folder/"report.json"
    db=folder/"comparison.sqlite3"
    if not report_file.is_file() or not db.is_file():
        raise OfflineAuditError("SAVED_ESI_COMPARISON_MISSING")
    snapshot=json.loads(report_file.read_text(encoding="utf-8"))
    if snapshot.get("run")!=run_id:
        raise OfflineAuditError("SAVED_ESI_RUN_MISMATCH")
    if (snapshot.get("status")!="PUBLIC_ESI_REGIONS_COMPLETE"
        or snapshot.get("full_universe_requested") is not True
        or snapshot.get("failed_regions")
        or snapshot.get("unverified_404_regions")):
        raise OfflineAuditError("ESI_FULL_PUBLIC_REGION_COVERAGE_NOT_PROVEN")
    output=folder/"depth_difference_audit.json"
    if output.exists():
        raise OfflineAuditError("DEPTH_DIFFERENCE_AUDIT_ALREADY_EXISTS")
    with closing(sqlite3.connect(f"file:{db.resolve().as_posix()}?mode=ro",
                                 uri=True)) as con:
        tables={x[0] for x in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"esi","everef"}.issubset(tables):
            raise OfflineAuditError("COMPARISON_TABLES_MISSING")
        n_esi=int(_one(con,"SELECT COUNT(*) FROM esi"))
        n_ref=int(_one(con,"SELECT COUNT(*) FROM everef"))
        if (n_esi!=snapshot.get("esi_unique_orders")
            or n_ref!= (snapshot.get("comparison") or {}).get("everef_orders")):
            raise OfflineAuditError("ARCHIVE_DOES_NOT_MATCH_RUN_REPORT")
        old_ref=snapshot.get("reference") or {}
        esi_unmatched=_unmatched_by_region(con,"esi","everef")
        ref_unmatched=_unmatched_by_region(con,"everef","esi")
        gaps=[_location_deltas(region,esi_unmatched,ref_unmatched)
              for region in ANOMALY_REGIONS]
        jita=_depth_audit(_book(con,"esi"),_book(con,"everef"))
        ranked=sorted([
            dict(region_id=int(region),
                 everef_only_count=sum(x["count"] for x in rows))
            for region,rows in ref_unmatched.items() if region is not None
        ],key=lambda x:(-x["everef_only_count"],x["region_id"]))[:12]
        shared = int(_one(con,"SELECT COUNT(*) FROM esi e "
                               "JOIN everef r ON e.order_id=r.order_id"))
        result={
            "status":"READ_ONLY_OFFLINE_DEPTH_AUDIT",
            "run":run_id,
            "input_esi":n_esi,
            "input_everef":n_ref,
            "matched_order_ids":shared,
            "matched_share_of_esi_pct":round(100*shared/n_esi,3) if n_esi else 0,
            "historical_everef_timestamp":old_ref.get("last_modified"),
            "esi_cache_freshness":snapshot.get("esi_cache_freshness"),
            "selected_region_unmatched_location_breakdown":gaps,
            "largest_everef_only_regions":ranked,
            "jita_buy_depth":jita,
            "network_calls":0,
            "same_v4_profit_algorithm_executed":False,
            "market_source_switched":False,
            "mail_sent":False,
            "decision":"KEEP_PRODUCTION_SOURCE_UNCHANGED",
            "next_gate":"Archive and verify all execution-critical fields (min_volume, range, route/cost basis) before running the SAME V4 engine on ESI and EVE Ref, not a simplified replacement.",
        }
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),
                      encoding="utf-8")
    return result,output


def main():
    ap=argparse.ArgumentParser(description="Offline ESI vs EVE Ref depth discrepancy audit; no API or mail")
    ap.add_argument("--data-root",type=Path,
                    default=Path.home()/"EVE-V4-Data")
    ap.add_argument("--run",required=True,
                    help="A fully completed one-shot ESI market validation run")
    args=ap.parse_args()
    result,path=audit(args.data_root,args.run)
    print(json.dumps({
        "status":result["status"],"run":result["run"],
        "matched_share_of_esi_pct":result["matched_share_of_esi_pct"],
        "largest_everef_only_regions":result["largest_everef_only_regions"],
        "jita_buy_depth":result["jita_buy_depth"],
        "decision":result["decision"]
    },ensure_ascii=False,indent=2))
    print("REPORT",path)


if __name__=="__main__":
    main()
