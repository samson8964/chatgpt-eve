"""Read-only SAME-engine ESI / EVE Ref V4 market opportunity parity gate.

NO live/mail/scheduler/contract/structure writes. Uses the current independent
ESI JSONL archived with min_volume/range and the immutable EVE Ref archive
PINNED in that ESI run's report. Evaluates only the existing V4 *approved
public NPC source stations* Amarr and Dodixie against Jita 4-4 BUY depth.
4-H, C-J and O4T require the existing authenticated structure transport and
cannot be represented by public regional ESI orders; they are excluded.

Uses EXACTLY v4.engine.market_proof, v4.market_execution.gross_depth_upper_bound,
v4.catalog.Catalog.volume and v4.deep_scan.haul/known_station_regions. Original
different-time EVE Ref vs ESI data remain historical research, never mail.
"""
from __future__ import annotations

import argparse
import bz2
import csv
import gzip
import json
import re
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path

from v4.catalog import Catalog, DEFAULT_CACHE
# deep_scan imports pandas/requests, unavailable in the lightweight
# reliability test runner. Import it only when REAL route evidence is needed.
from v4.market_depth import JITA
from v4.engine import Order, Policy, market_proof, quarantine_snapshot_candidate, _well_formed_zero_remaining
from v4.market_execution import gross_depth_upper_bound

# Same two permitted public NPC sources as deep_scan.KNOWN_STATIONS.
# Assert this mapping in full-runtime tests; no expansion to other locations.
SOURCES=(60008494,60011866)
VALIDATED_RUN=re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")
POLICY=Policy()
REQUIRED={"order_id","location_id","type_id","is_buy_order","price",
          "volume_remain","min_volume","range"}
ACTIVE_STATUSES={"COMPLETE","EMPTY_MARKET_CONFIRMED"}


class ParityError(RuntimeError):
    pass


def _selected(raw):
    """Keep only source station asks / Jita buy; no false broad venue scope."""
    try:
        loc=int(raw["location_id"])
    except (KeyError,TypeError,ValueError,OverflowError) as exc:
        raise ParityError("MARKET_LOCATION_FIELD_INVALID") from exc
    if loc not in (JITA,*SOURCES):
        return False
    side=raw.get("is_buy_order")
    if isinstance(side,bool):
        buy=side
    elif str(side).strip().lower() in ("true","1"):
        buy=True
    elif str(side).strip().lower() in ("false","0"):
        buy=False
    else:
        raise ParityError("MARKET_SIDE_INVALID")
    return (loc==JITA and buy) or (loc in SOURCES and not buy)


def _append_selected(raw,market,label):
    try:
        order=Order.parse(raw)  # production V4 parser, preserving min + range
    except (KeyError,ValueError,TypeError,OverflowError) as exc:
        if _well_formed_zero_remaining(raw):
            return "ZERO_REMAINING"
        raise ParityError(f"{label}_INVALID_APPROVED_MARKET_ORDER:"
                          f"order_id={str(raw.get('order_id','?'))[:22]}:"
                          f"{type(exc).__name__}") from exc
    if (order.location_id,order.type_id,order.buy) not in market:
        market[(order.location_id,order.type_id,order.buy)]=[]
    market[(order.location_id,order.type_id,order.buy)].append(order)
    return "ACTIVE"


def _load_esi(folder,report):
    results=report["regions"]
    if len(results)!=report["universe_regions"] or any(
            r["status"] not in ACTIVE_STATUSES for r in results):
        raise ParityError("ESI_REGION_COVERAGE_INCOMPLETE")
    needed={"min_volume","range","volume_total"}
    if not needed.issubset(report.get("archive_execution_fields") or []):
        raise ParityError("ESI_EXECUTION_FIELDS_NOT_ARCHIVED_RESCAN_REQUIRED")
    market=defaultdict(list)
    metrics=Counter()
    ids=set()
    for region in results:
        rid=int(region["region_id"])
        path=folder/"regions"/f"{rid}.jsonl.gz"
        if not path.is_file():
            raise ParityError(f"ESI_REGION_ARCHIVE_MISSING:{rid}")
        n=0
        with gzip.open(path,"rt",encoding="utf-8") as stream:
            for line in stream:
                r=json.loads(line)
                if not REQUIRED.issubset(r):
                    raise ParityError("ESI_ROW_EXECUTION_FIELDS_MISSING")
                if int(r["region_id"])!=rid:
                    raise ParityError("ESI_ORDER_REGION_MISMATCH")
                oid=int(r["order_id"])
                if oid in ids:
                    raise ParityError("ESI_DUPLICATE_ORDER_ID")
                ids.add(oid)
                n+=1
                if _selected(r):
                    status=_append_selected(r,market,"ESI")
                    metrics[status]+=1
        if n!=int(region["orders"]):
            raise ParityError(f"ESI_REGION_ARCHIVE_COUNT_MISMATCH:{rid}")
        metrics["all_archived"]+=n
    if metrics["all_archived"]!=int(report["esi_unique_orders"]):
        raise ParityError("ESI_TOTAL_ORDER_COUNT_MISMATCH")
    return market,dict(metrics)


def _load_ref(path):
    """EVE Ref immutable archived CSV; never fetch, never replace source."""
    market=defaultdict(list)
    metrics=Counter()
    selected_ids=set()
    with bz2.open(path,"rt",encoding="utf-8",newline="") as stream:
        reader=csv.DictReader(stream)
        if not REQUIRED.issubset(set(reader.fieldnames or ())):
            raise ParityError("EVEREF_EXECUTION_FIELDS_NOT_AVAILABLE")
        for row in reader:
            metrics["all_archived"]+=1
            if not _selected(row):
                continue
            oid=int(row["order_id"])
            if oid in selected_ids:
                raise ParityError("EVEREF_SELECTED_DUPLICATE_ORDER_ID")
            selected_ids.add(oid)
            status=_append_selected(row,market,"EVEREF")
            metrics[status]+=1
    if metrics["all_archived"]==0:
        raise ParityError("EVEREF_MARKET_ARCHIVE_EMPTY")
    return market,dict(metrics)


def _sort_books(market):
    for (loc,typ,buy),book in market.items():
        book.sort(key=lambda o:(-o.price if buy else o.price,o.order_id))
    return market


def _model(market,catalog,haul_fn):
    """Same V4 public-NPC source, two-sided depth gate and market_proof."""
    books=_sort_books(market)
    proofs={}
    counts=Counter()
    keys=sorted((loc,typ) for loc,typ,buy in books
                if not buy and loc in SOURCES)
    for loc,typ in keys:
        asks=books[(loc,typ,False)]
        bids=books.get((JITA,typ,True),())
        if not bids:
            counts["NO_JITA_BUY"]+=1
            continue
        if asks[0].price>=bids[0].price:
            counts["NOT_PRICE_CROSSED"]+=1
            continue
        if gross_depth_upper_bound(asks,bids)<POLICY.profit_floor:
            counts["BELOW_DEPTH_GROSS_CEILING"]+=1
            continue
        counts["PREFILTER_PASSED"]+=1
        volume=catalog.volume(typ)
        haul_for_units=(lambda n,source=loc,item_volume=volume:
                        haul_fn(source,JITA,float(item_volume)*n)
                        if item_volume else None)
        p=market_proof(
            asks,bids,source_location=loc,destination_location=JITA,
            type_id=int(typ),volume_m3=volume,haul_isk=None,
            haul_for_units=haul_for_units,policy=POLICY,
            allowed=True,fresh=True)
        passed=p.get("status")=="MAIL"
        counts["FORMAL_POLICY_PASSED" if passed else
               "RESEARCH_"+p.get("reason","UNKNOWN")]+=1
        # Never allow the formal MAIL state into a shadow research artifact.
        quarantine_snapshot_candidate(p)
        proofs[f"{loc}:{typ}"]={
            "source_station":loc,"type_id":typ,
            "policy_passed_shadow_only":passed,
            "reason":p.get("reason"),"quantity":p.get("quantity"),
            "profit":p.get("profit"),"roi":p.get("roi"),
            "stress_profit":p.get("stress_profit"),
            "haul":p.get("haul"),"source_vwap":p.get("source_vwap_isk_per_unit"),
            "jita_vwap":p.get("jita_vwap_isk_per_unit"),
            "ask_order_ids":p.get("ask_order_ids"),
            "bid_order_ids":p.get("bid_order_ids"),
        }
    counts["APPROVED_SOURCE_SELL_TYPES"]=len(keys)
    return proofs,dict(counts)


def _diff(lhs,rhs):
    keys=sorted(set(lhs)|set(rhs))
    categories=Counter()
    rows=[]
    for key in keys:
        a=lhs.get(key)
        b=rhs.get(key)
        a_pass=bool(a and a["policy_passed_shadow_only"])
        b_pass=bool(b and b["policy_passed_shadow_only"])
        category=("BOTH_FORMAL_GATE" if a_pass and b_pass else
                  "ESI_ONLY_FORMAL_GATE" if a_pass else
                  "EVEREF_ONLY_FORMAL_GATE" if b_pass else
                  "NEITHER_FORMAL_GATE")
        categories[category]+=1
        if a_pass or b_pass:
            rows.append({
                "station_type":key,"classification":category,
                "esi":a,"everef":b,
                "net_profit_difference_isk":(
                    round(a["profit"]-b["profit"],2)
                    if a and b and a["profit"] is not None and
                    b["profit"] is not None else None),
            })
    return {"classification_counts":dict(categories),
            "all_gate_positive_pairs":rows}


def _route_evidence():
    # Same V4 transport model as deep_scan.py, with its own official route
    # metadata calls. No market, contract or mail network calls.
    from v4.deep_scan import KNOWN_STATIONS, known_station_regions, _secure_route_jumps
    if SOURCES!=(KNOWN_STATIONS["amarr"],KNOWN_STATIONS["dodixie"]):
        raise ParityError("PUBLIC_NPC_STATION_SCOPE_DRIFT")
    stations=known_station_regions()
    output={}
    for station in SOURCES:
        s=stations.get(station) or {}
        jita=stations.get(JITA) or {}
        if "system" not in s or "system" not in jita:
            raise ParityError("OFFICIAL_STATION_METADATA_UNAVAILABLE")
        jumps=_secure_route_jumps(int(s["system"]),int(jita["system"]))
        if not isinstance(jumps,int) or jumps<=0:
            raise ParityError("OFFICIAL_ROUTE_UNAVAILABLE")
        output[str(station)]={"source_system":s["system"],
                              "jita_system":jita["system"],
                              "secure_route_jumps":jumps}
    return stations,output


def audit(root,run_id,*,catalog=None,haul_fn=None,route_evidence=None):
    if not VALIDATED_RUN.fullmatch(run_id):
        raise ParityError("INVALID_ESI_RUN_ID")
    folder=Path(root)/"esi-parallel-validation"/run_id
    report_path=folder/"report.json"
    if not report_path.is_file():
        raise ParityError("ESI_REPORT_NOT_FOUND")
    report=json.loads(report_path.read_text("utf-8"))
    if (report.get("run")!=run_id or
            report.get("status")!="PUBLIC_ESI_REGIONS_COMPLETE" or
            report.get("full_universe_requested") is not True or
            report.get("failed_regions") or report.get("unverified_404_regions")):
        raise ParityError("ESI_ARCHIVE_NOT_FULLY_VERIFIED")
    pinned=report.get("reference") or {}
    ref_run=pinned.get("run")
    if not isinstance(ref_run,str) or not VALIDATED_RUN.fullmatch(ref_run):
        raise ParityError("PINNED_EVEREF_REFERENCE_MISSING")
    reference=Path(root)/"runs"/ref_run/"source"/"market_orders.csv.bz2"
    manifest=Path(root)/"runs"/ref_run/"manifest.json"
    if not reference.is_file() or not manifest.is_file():
        raise ParityError("PINNED_EVEREF_SNAPSHOT_MISSING")
    if json.loads(manifest.read_text("utf-8")).get("status")!="SHADOW_RECORDED":
        raise ParityError("PINNED_EVEREF_RUN_NOT_COMPLETED")
    output=folder/"same_engine_market_comparison.json"
    if output.exists():
        raise ParityError("SAME_ENGINE_COMPARISON_ALREADY_EXISTS")
    if catalog is None:
        if not DEFAULT_CACHE.is_file():
            raise ParityError("LOCAL_V4_CATALOG_MISSING_RUN_REGULAR_V4_FIRST")
        catalog=Catalog.load(DEFAULT_CACHE)
    esi,esi_counts=_load_esi(folder,report)
    everef,ref_counts=_load_ref(reference)
    if haul_fn is None:
        stations,route_evidence=_route_evidence()
        from v4.deep_scan import haul  # the unmodified production V4 model
        haul_fn=lambda src,dest,volume:haul(src,dest,volume,stations)
    if route_evidence is None:
        route_evidence={"injected_for_offline_test":True}
    left,lc=_model(esi,catalog,haul_fn)
    right,rc=_model(everef,catalog,haul_fn)
    compared=_diff(left,right)
    outcome={
        "status":"SHADOW_SAME_V4_ENGINE_PUBLIC_NPC_ONLY",
        "run":run_id,"reference_run":ref_run,
        "esi_orders":esi_counts,"everef_orders":ref_counts,
        "source_scope":"APPROVED_PUBLIC_NPC_AMARR_DODIXIE_TO_JITA_ONLY",
        "structures_4h_cj_o4t":"NOT_EVALUATED_EXISTING_AUTHORIZED_SCANS_UNCHANGED",
        "snapshot_timestamps":{
            "esi":report.get("esi_cache_freshness"),
            "everef":pinned.get("last_modified")},
        "economic_logic":"v4.engine.market_proof + v4.market_execution.gross_depth_upper_bound + v4.deep_scan.haul",
        "policy":{
            "profit_floor_isk":POLICY.profit_floor,
            "min_roi":POLICY.min_roi,
            "min_density_isk_per_m3":POLICY.min_density,
            "sales_tax":POLICY.sales_tax},
        "route_evidence":route_evidence,
        "esi_model_counts":lc,"everef_model_counts":rc,
        "comparison":compared,
        "network_order_requests":0,
        "possible_official_metadata_route_requests":(
            False if route_evidence.get("injected_for_offline_test")
            else True),
        "mail_sent":False,"production_market_source_changed":False,
        "decision":"DO_NOT_SWITCH_PRODUCTION",
        "limitations":"Different-time ESI and EVE Ref market snapshots. Public NPC stations only. No contracts, private Upwell books or real trade execution. Policy passes are research-only and never delivered."
    }
    output.write_text(json.dumps(outcome,ensure_ascii=False,indent=2),
                      encoding="utf-8")
    return outcome,output


def main():
    p=argparse.ArgumentParser(description="V4 same-engine historical ESI vs EVE Ref public NPC market proof shadow; no emails")
    p.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    p.add_argument("--run",required=True)
    args=p.parse_args()
    result,path=audit(args.data_root,args.run)
    print(json.dumps({k:result[k] for k in (
        "status","run","esi_model_counts","everef_model_counts",
        "source_scope","mail_sent","production_market_source_changed",
        "decision")},ensure_ascii=False,indent=2))
    print("CLASSIFICATIONS",json.dumps(result["comparison"]["classification_counts"],
                                        ensure_ascii=False))
    print("REPORT",path)


if __name__=="__main__":
    main()
