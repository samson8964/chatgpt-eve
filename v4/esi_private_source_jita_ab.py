"""One-shot, authorized, READ-ONLY private-source / Jita-bid historical A/B.

The SAME freshly acquired 4-H, C-J, O4T SELL books are evaluated against
two old Jita 4-4 BUY snapshots: ESI independently archived and pinned EVE Ref.
No private order rows, access keys or bridge response bodies are persisted.
All outputs are independent research summaries; there is NO mail, no task,
no production source change, and no assertion of live tradability.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from v4.catalog import Catalog, DEFAULT_CACHE
from v4.engine import Order, Policy, market_proof, _well_formed_zero_remaining
from v4.market_execution import gross_depth_upper_bound
from v4.esi_same_engine_market_shadow import (
    ParityError, _load_esi, _load_ref, _sort_books, VALIDATED_RUN, JITA
)
from v4.esi_parallel_validation import _http_time

# Existing V4 deep_scan.py station IDs (validated again when fetching in
# production runtime). Never broaden scope to unknown player structures.
STRUCTURES={
    "4-H":1053970513596,
    "C-J":1049588174021,
    "O4T":1040804972352,
}
POLICY=Policy()


def _fetch_authorized_once():
    """Keep bridge access token only in memory. No secret in CLI arguments."""
    from v4.deep_scan import all_structure_orders, STRUCTURES as live_ids
    if {k:v[0] for k,v in live_ids.items()}!={
            "four_h":STRUCTURES["4-H"],
            "cj":STRUCTURES["C-J"],
            "o4t":STRUCTURES["O4T"]}:
        raise ParityError("PRIVATE_STRUCTURE_SCOPE_DRIFT")
    key=os.environ.get("EVE_MARKET_API_KEY")
    if not key and os.name=="nt":
        from v4.local_bridge_auth import get_bridge_key
        key=get_bridge_key()
    if not key:
        raise ParityError("PRIVATE_BRIDGE_AUTH_MISSING")
    return all_structure_orders(key)


def _fresh_jita_books(root,run_id,*,now=None,max_age_minutes=15):
    """Offline load a fresh, verified ONE-REGION ESI capture: The Forge.

    No extra network requests; leaves original ESI validation archive intact.
    Requires freshness *at comparison time*, not just at collection time.
    """
    if not isinstance(run_id,str) or not VALIDATED_RUN.fullmatch(run_id):
        raise ParityError("INVALID_JITA_ESI_VALIDATION_RUN_ID")
    folder=Path(root)/"esi-parallel-validation"/run_id
    report_file=folder/"report.json"
    if not report_file.is_file():
        raise ParityError("FRESH_JITA_ESI_REPORT_MISSING")
    report=json.loads(report_file.read_text("utf-8"))
    if (report.get("run")!=run_id or
            report.get("status")!="PARTIAL_REGION_TEST_ONLY"
            or report.get("requested_region_ids")!=[10000002]
            or report.get("attempted_regions")!=1
            or report.get("full_universe_requested") is not False
            or report.get("failed_regions") or
            report.get("unverified_404_regions")
            or len(report.get("regions") or [])!=1):
        raise ParityError("FRESH_JITA_ESI_TARGETED_COVERAGE_INVALID")
    region=report["regions"][0]
    if (region.get("region_id")!=10000002 or
            region.get("status")!="COMPLETE"
            or int(region.get("pages") or 0)<1):
        raise ParityError("FRESH_JITA_ESI_REGION_INCOMPLETE")
    required={"order_id","region_id","location_id","type_id",
              "is_buy_order","price","volume_remain","min_volume","range",
              "volume_total"}
    if not required.issubset(report.get("archive_execution_fields") or []):
        raise ParityError("FRESH_JITA_ESI_EXECUTION_FIELDS_MISSING")
    stamp=_http_time(region.get("last_modified"))
    reference_time=now or datetime.now(timezone.utc)
    age_minutes=(reference_time-stamp).total_seconds()/60
    if not (0<=age_minutes<=max_age_minutes):
        raise ParityError("FRESH_JITA_ESI_SNAPSHOT_TOO_OLD_OR_CLOCK_SKEW")
    archive=folder/"regions"/"10000002.jsonl.gz"
    if not archive.is_file():
        raise ParityError("FRESH_JITA_ESI_ARCHIVE_MISSING")
    books=defaultdict(list)
    seen=set()
    metrics=Counter()
    with gzip.open(archive,"rt",encoding="utf-8") as stream:
        for line in stream:
            row=json.loads(line)
            if not isinstance(row,dict) or not required.issubset(row):
                raise ParityError("FRESH_JITA_ESI_ORDER_FIELDS_MISSING")
            if int(row["region_id"])!=10000002:
                raise ParityError("FRESH_JITA_ESI_REGION_ROW_MISMATCH")
            oid=int(row["order_id"])
            if oid in seen:
                raise ParityError("FRESH_JITA_ESI_DUPLICATE_ORDER")
            seen.add(oid)
            metrics["forge_active_orders"]+=1
            if int(row["location_id"])==JITA and str(row["is_buy_order"]).lower() in (
                    "1","true"):
                try:
                    order=Order.parse(row)
                except (KeyError,TypeError,ValueError,OverflowError) as exc:
                    raise ParityError("FRESH_JITA_ESI_INVALID_JITA_BUY") from None
                books[(JITA,order.type_id,True)].append(order)
                metrics["jita_buy_orders"]+=1
    if (metrics["forge_active_orders"]!=int(region["orders"])
            or metrics["forge_active_orders"]!=int(report["esi_unique_orders"])
            or not metrics["jita_buy_orders"]):
        raise ParityError("FRESH_JITA_ESI_ARCHIVE_COUNT_MISMATCH")
    _sort_books(books)
    metadata={
        "archive_run":run_id,
        "region_id":10000002,
        "verified_pages":int(region["pages"]),
        "forge_active_orders":metrics["forge_active_orders"],
        "jita_buy_orders":metrics["jita_buy_orders"],
        "last_modified":stamp.isoformat(),
        "age_at_private_comparison_minutes":round(age_minutes,3),
        "max_allowed_age_minutes":max_age_minutes,
        "archive_reused_read_only":True,
    }
    return books,dict(metrics),metadata


def _private_asks(raw,health):
    if not isinstance(health,dict) or set(health)!={"four_h","cj","o4t"}:
        raise ParityError("PRIVATE_STRUCTURE_COVERAGE_UNVERIFIED")
    expected={"four_h":STRUCTURES["4-H"],"cj":STRUCTURES["C-J"],
              "o4t":STRUCTURES["O4T"]}
    for name,location in expected.items():
        lane=health[name]
        if (not isinstance(lane,dict) or lane.get("status")!="COMPLETE"
                or int(lane.get("location",-1))!=location
                or int(lane.get("orders",-1))<0):
            raise ParityError("PRIVATE_STRUCTURE_LANE_FAILED:"+name)
    if sum(int(health[x]["orders"]) for x in expected)!=len(raw):
        raise ParityError("PRIVATE_STRUCTURE_ORDER_COUNT_MISMATCH")
    seen=set()
    books=defaultdict(list)
    traces=defaultdict(list)
    counts=Counter()
    for entry in raw:
        if not isinstance(entry,dict):
            raise ParityError("PRIVATE_STRUCTURE_NON_OBJECT_ROW")
        try:
            order=Order.parse(entry)
        except (TypeError,ValueError,KeyError,OverflowError) as exc:
            if _well_formed_zero_remaining(entry):
                counts["zero_remaining_excluded"]+=1
                continue
            raise ParityError("PRIVATE_STRUCTURE_MALFORMED_ACTIVE_ORDER:"
                              +type(exc).__name__) from None
        if order.location_id not in STRUCTURES.values():
            raise ParityError("PRIVATE_STRUCTURE_ORDER_LOCATION_MISMATCH")
        if order.order_id in seen:
            raise ParityError("PRIVATE_STRUCTURE_DUPLICATE_ORDER_ID")
        seen.add(order.order_id)
        counts["all_active_orders"]+=1
        if not order.buy:
            books[(order.location_id,order.type_id,False)].append(order)
            # Cryptographic provenance only. Never write individual
            # private order price, ID or row body to the JSON output.
            traces[order.location_id].append((
                order.order_id,order.type_id,order.price,
                order.remaining,order.minimum,order.range))
            counts["active_sell_orders"]+=1
        else:
            counts["active_buy_orders_excluded"]+=1
    if (counts["all_active_orders"]+counts["zero_remaining_excluded"]
            !=len(raw)):
        raise ParityError("PRIVATE_STRUCTURE_ACCOUNTING_MISMATCH")
    fingerprints={
        str(loc):hashlib.sha256(json.dumps(
            sorted(rows),separators=(",",":"),ensure_ascii=False
        ).encode("utf-8")).hexdigest()
        for loc,rows in traces.items()
    }
    for loc in STRUCTURES.values():
        fingerprints.setdefault(str(loc),hashlib.sha256(b"[]").hexdigest())
    return _sort_books(books),dict(counts),fingerprints


def _evaluate(asks,public_books,catalog,haul_fn):
    """Run unmodified market_proof with the same structure SELL inputs."""
    counters=Counter()
    by_station=defaultdict(Counter)
    proofs={}
    for (location,typ,buy),orders in sorted(asks.items()):
        if buy or location not in STRUCTURES.values():
            raise ParityError("PRIVATE_SELL_SCOPE_MISMATCH")
        label=next(k for k,v in STRUCTURES.items() if v==location)
        by_station[label]["sell_types"]+=1
        bids=public_books.get((JITA,typ,True),())
        if not bids:
            counters["NO_JITA_BUY"]+=1
            by_station[label]["NO_JITA_BUY"]+=1
            continue
        if orders[0].price>=bids[0].price:
            counters["NOT_PRICE_CROSSED"]+=1
            by_station[label]["NOT_PRICE_CROSSED"]+=1
            continue
        if gross_depth_upper_bound(orders,bids)<POLICY.profit_floor:
            counters["BELOW_GROSS_DEPTH_CEILING"]+=1
            by_station[label]["BELOW_GROSS_DEPTH_CEILING"]+=1
            continue
        counters["PREFILTER_PASSED"]+=1
        by_station[label]["PREFILTER_PASSED"]+=1
        volume=catalog.volume(typ)
        per_lot_haul=lambda units,source=location,per_unit=volume:(
            haul_fn(source,JITA,float(units)*per_unit)
            if per_unit is not None else None)
        proof=market_proof(orders,bids,source_location=location,
            destination_location=JITA,type_id=typ,volume_m3=volume,
            haul_isk=None,haul_for_units=per_lot_haul,policy=POLICY,
            allowed=True,fresh=True)
        eligible=proof.get("status")=="MAIL"
        counters["MODEL_PASS_RESEARCH_ONLY" if eligible else
                 "REJECT_"+str(proof.get("reason","UNKNOWN"))]+=1
        by_station[label]["MODEL_PASS_RESEARCH_ONLY" if eligible
                          else "REJECTED"]+=1
        # Never call an outbox or carry a MAIL-tagged proof into persistence.
        proofs[f"{label}:{typ}"]={
            "station":label,"station_id":location,"type_id":typ,
            "hypothetical_model_pass":eligible,
            "reason":proof.get("reason"),
            "quantity":proof.get("quantity"),
            "net_profit_isk":proof.get("profit"),
            "roi":proof.get("roi"),
            "stress_profit_isk":proof.get("stress_profit"),
            "haul_isk":proof.get("haul"),
            "source_vwap_isk":proof.get("source_vwap_isk_per_unit"),
            "jita_buy_vwap_isk":proof.get("jita_vwap_isk_per_unit"),
        }
    counters["evaluated_private_sell_type_pairs"]=len(asks)
    return proofs,dict(counters),{k:dict(v) for k,v in by_station.items()}


def _compare(a,b):
    keys=sorted(set(a)|set(b))
    cat=Counter()
    candidates=[]
    for k in keys:
        x=a.get(k)
        y=b.get(k)
        xp=bool(x and x["hypothetical_model_pass"])
        yp=bool(y and y["hypothetical_model_pass"])
        label=("BOTH_PASS" if xp and yp else "ESI_ONLY_PASS" if xp
               else "EVEREF_ONLY_PASS" if yp else "NEITHER_PASS")
        cat[label]+=1
        # No individual private order details are emitted. Only aggregate
        # evaluated lot numbers / prices for these prefilter candidates.
        candidates.append({
            "station_type":k,"classification":label,
            "esi":x,"everef":y,
            "net_profit_difference_isk":(
                round(x["net_profit_isk"]-y["net_profit_isk"],2)
                if x and y and x["net_profit_isk"] is not None
                and y["net_profit_isk"] is not None else None)})
    return {"classification_counts":dict(cat),
            "historical_prefilter_union":len(keys),
            "candidate_differences":candidates}


def audit(root,run_id,*,fetch_structures=None,catalog=None,haul_fn=None,
          fresh_jita_run=None):
    if not VALIDATED_RUN.fullmatch(run_id):
        raise ParityError("INVALID_ESI_RUN_ID")
    root=Path(root)
    parent=root/"esi-parallel-validation"/run_id
    report_file=parent/"report.json"
    if not report_file.is_file():
        raise ParityError("ESI_RUN_REPORT_MISSING")
    report=json.loads(report_file.read_text(encoding="utf-8"))
    if (report.get("run")!=run_id or
            report.get("status") not in (
                "PUBLIC_ESI_REGIONS_COMPLETE",
                "SHADOW_MULTI_EPOCH_REPAIRED_COVERAGE")
            or report.get("failed_regions") or
            report.get("unverified_404_regions")):
        raise ParityError("ESI_REFERENCE_COVERAGE_NOT_COMPLETE")
    pin=report.get("reference") or {}
    ref_run=pin.get("run")
    if not isinstance(ref_run,str) or not VALIDATED_RUN.fullmatch(ref_run):
        raise ParityError("PINNED_EVEREF_REFERENCE_MISSING")
    ref_parent=root/"runs"/ref_run
    ref=ref_parent/"source"/"market_orders.csv.bz2"
    manifest=ref_parent/"manifest.json"
    if not ref.is_file() or not manifest.is_file():
        raise ParityError("PINNED_EVEREF_REFERENCE_FILES_MISSING")
    if json.loads(manifest.read_text("utf-8")).get("status")!="SHADOW_RECORDED":
        raise ParityError("PINNED_EVEREF_REFERENCE_INCOMPLETE")
    if catalog is None:
        if not DEFAULT_CACHE.is_file():
            raise ParityError("LOCAL_CATALOG_MISSING")
        catalog=Catalog.load(DEFAULT_CACHE)
    if haul_fn is None:
        from v4.deep_scan import haul
        haul_fn=lambda source,dest,volume:haul(source,dest,volume,{})
    # Read historical EVE Ref once. Private authenticated asks are fetched
    # once and are IDENTICAL for both comparison branches.
    old,old_counts=_load_ref(ref)
    if fetch_structures is None:
        fetch_structures=_fetch_authorized_once
    private_started=datetime.now(timezone.utc)
    raw,health=fetch_structures()
    private_finished=datetime.now(timezone.utc)
    asks,counts,hashes=_private_asks(raw,health)
    if fresh_jita_run:
        esi,esi_counts,fresh_metadata=_fresh_jita_books(
            root,fresh_jita_run,now=private_finished)
    else:
        esi,esi_counts=_load_esi(parent,report)
        fresh_metadata=None
    if not asks:
        raise ParityError("NO_AUTHORIZED_PRIVATE_SELL_ORDERS")
    new_proofs,new_counts,new_station=_evaluate(asks,esi,catalog,haul_fn)
    old_proofs,old_counts_by_model,old_station=_evaluate(asks,old,catalog,haul_fn)
    diff=_compare(new_proofs,old_proofs)
    now=datetime.now(timezone.utc)
    result={
        "status":("READ_ONLY_PRIVATE_SOURCE_FRESH_JITA_BUY_AB"
                  if fresh_jita_run else "READ_ONLY_PRIVATE_SOURCE_FIXED_JITA_BUY_AB"),
        "run":run_id,
        "generated_at_utc":now.isoformat(),
        "scope":"4-H_C-J_O4T_SAME_AUTHORIZED_PRIVATE_ASKS_VS_HISTORICAL_JITA_BUYS",
        "authenticated_ask_collection_utc":private_finished.isoformat(),
        "private_collection_started_utc":private_started.isoformat(),
        "private_collection_finished_utc":private_finished.isoformat(),
        "private_market_lane_health":{
            label:{
                "status":health[key]["status"],
                "orders":health[key]["orders"],
                "pages":health[key]["pages"],
            }
            for label,key in [("4-H","four_h"),("C-J","cj"),("O4T","o4t")]},
        "private_market_counts":counts,
        "private_sell_snapshot_sha256_by_location":hashes,
        "esi_public_count":(esi_counts.get("forge_active_orders")
                            if fresh_jita_run else esi_counts.get("all_archived")),
        "esi_price_feed_kind":("FRESH_VERIFIED_THE_FORGE_REGION_JITA_BUYS"
                               if fresh_jita_run else "HISTORICAL_MULTIREGION"),
        "fresh_jita_snapshot_evidence":fresh_metadata,
        "everef_public_count":old_counts.get("all_archived"),
        "esi_cache_times":(fresh_metadata or report.get("esi_cache_freshness")),
        "everef_timestamp":pin.get("last_modified"),
        "esi_model_counts":new_counts,
        "everef_model_counts":old_counts_by_model,
        "esi_by_station":new_station,
        "everef_by_station":old_station,
        "comparison":diff,
        "model":"UNMODIFIED_V4_market_proof_and_gross_depth_upper_bound_and_haul",
        "profit_floor_isk":POLICY.profit_floor,
        "minimum_roi":POLICY.min_roi,
        "minimum_density_per_m3":POLICY.min_density,
        "sales_tax":POLICY.sales_tax,
        "private_raw_rows_persisted":False,
        "order_book_public_market_requests":0,
        "private_bridge_requests":"ONE_COMPLETE_AUTHORIZED_COLLECTION",
        "mail_sent":False,
        "production_source_changed":False,
        "decision":"DO_NOT_SWITCH_PRODUCTION",
        "warning":("Authorised private SELL orders captured now and valued with a verified recently archived ESI Jita BUY snapshot against an old EVE Ref snapshot. The fresh ESI and private sources are not atomic/live-confirmed; old EVE Ref is from a different epoch. Never infer executable LIVE opportunity, grant a production source switch, or send a signal."
                   if fresh_jita_run else
                   "Authorised private SELL orders collected once now, both Jita BUY books are historical from different epochs. Do not infer LIVE profitability, a production source switch, or structure-side ESI-vs-EVERef parity from this research."),
    }
    save=parent/(("private_source_jita_fresh_ab_" if fresh_jita_run
                  else "private_source_jita_ab_")
                 +now.strftime("%Y%m%dT%H%M%SZ")
                 +"-"+uuid.uuid4().hex[:8]+".json")
    with save.open("x",encoding="utf-8") as f:
        json.dump(result,f,ensure_ascii=False,indent=2)
    return result,save


def main():
    p=argparse.ArgumentParser(
        description="Read-only private 4-H C-J O4T SAME source SELL book vs two historical Jita BUY feeds; no email")
    p.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    p.add_argument("--run",required=True)
    p.add_argument("--fresh-jita-run",default=None,
                   help="NEW optional: exact run ID of a recently verified "
                        "one-region ESI 10000002 capture, freshness <= 15 minutes; "
                        "compares it to pinned EVE Ref using identical private asks")
    args=p.parse_args()
    result,output=audit(args.data_root,args.run,
                        fresh_jita_run=args.fresh_jita_run)
    print(json.dumps({
        "status":result["status"],"run":result["run"],
        "private_market_counts":result["private_market_counts"],
        "esi_model_counts":result["esi_model_counts"],
        "everef_model_counts":result["everef_model_counts"],
        "classifications":result["comparison"]["classification_counts"],
        "mail_sent":result["mail_sent"],
        "production_source_changed":result["production_source_changed"],
        "esi_price_feed_kind":result["esi_price_feed_kind"],
        "fresh_jita_snapshot_evidence":result["fresh_jita_snapshot_evidence"],
        "decision":result["decision"],
    },ensure_ascii=False,indent=2))
    print("REPORT",output)


if __name__=="__main__":
    main()
