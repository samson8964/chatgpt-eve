"""Offline real multi-item contract valuation cross-check against Jita buy depth.

Unlike isolated fixtures, this samples ACTUAL contract IDs, actual item rows,
and actual Jita buy order IDs/prices from ONE completed V4 source snapshot.
No ESI, Cloudflare, email, scheduled runs, writes or production scans.

A generic multi-item contract is evidence for the Jita depth/price/fee model,
NOT proof of real mixed PLEX-crate+ordinary-goods coverage when none exist.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from v4.celebration_crate_radar import (
    BOXES, JITA, PLEX, TAX, _cash_out, _books, _orders, _time,
)
from v4.catalog import Catalog, DEFAULT_CACHE
from v4.sources import contract_dataframes, market_dataframe
from v4.npc_station_catalog import load_catalog
from v4.structure_registry import STRUCTURES
from v4.deep_scan import haul

MAX_AUDIT_CANDIDATES = 350
MAX_TYPES = 16


def _int(value):
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
        if not math.isfinite(n) or n != int(n):
            return None
        return int(n)
    except (ValueError, TypeError, OverflowError):
        return None


def _float(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _true(v):
    return str(v).strip().lower() in ("true", "t", "1")


def _manual_match(orders, quantity):
    """Independent order-depth loop, not v4.engine.fill_book."""
    remain = quantity
    value = 0.0
    used = []
    sorted_orders = sorted(orders,key=lambda o:(-o.price,o.order_id))
    for o in sorted_orders:
        if remain <= 0:
            break
        qty = min(o.remaining,remain)
        if qty < o.minimum:
            continue
        remain -= qty
        value += qty * o.price
        used.append({"order_id":o.order_id,"matched_units":qty,
                     "unit_bid_isk":o.price})
    return {"matched_units":quantity-remain, "gross_isk":value,
            "remaining_units_unpriced":remain, "fills":used[:6]}


def _contract_candidate_rows(contracts, items, *, locations, catalog, at):
    """Select only valid, no-request physical exchange bundles."""
    by_contract = defaultdict(lambda: defaultdict(int))
    requested = set()
    for row in items:
        cid, tid, qty = (_int(row.get(x)) for x in
                         ("contract_id","type_id","quantity"))
        if cid is None:
            continue
        if not _true(row.get("is_included")):
            requested.add(cid)
        elif tid is not None and qty is not None and qty > 0:
            by_contract[cid][tid] += qty
    out = []
    counts = Counter()
    for raw in contracts:
        cid, loc = _int(raw.get("contract_id")), _int(raw.get("start_location_id"))
        if cid is None or loc not in locations:
            continue
        goods = by_contract.get(cid) or {}
        if len(goods) < 2:
            continue
        counts["multi_type_in_scope"] += 1
        if cid in requested:
            counts["with_requested_items_excluded"] += 1
            continue
        if str(raw.get("type","")).lower() != "item_exchange":
            counts["not_item_exchange"] += 1
            continue
        if str(raw.get("status","outstanding")).lower() not in ("outstanding",""):
            counts["not_outstanding"] += 1
            continue
        expiration = raw.get("date_expired")
        if expiration is not None and str(expiration).strip() not in ("","None"):
            parsed = _time(expiration)
            if parsed is None or parsed < at:
                counts["expired_or_invalid_date"] += 1
                continue
        price = _float(raw.get("price"))
        if price is None or price < 0:
            counts["invalid_price"] += 1
            continue
        if any(catalog.classification(tid) == "blueprint_type" for tid in goods):
            counts["contains_blueprint_excluded"] += 1
            continue
        if len(goods) > MAX_TYPES:
            counts["over_max_types_for_audit"] += 1
            continue
        out.append({"contract_id":cid, "source_location":loc,
                    "contract_price_isk":price, "goods":dict(goods),
                    "contains_approved_plex_crate":bool(set(goods) & set(BOXES))})
    counts["eligible_nonblueprint_no_requests"] = len(out)
    # Keep actual crate bundles first, then Jita self-contained and diversified
    # examples; never use a synthetic crate to claim real data validation.
    out.sort(key=lambda r:(not r["contains_approved_plex_crate"],
                           r["source_location"] != JITA,
                           -len(r["goods"]), r["contract_id"]))
    return out, counts


def audit_rows(contracts, items, market, *, catalog, locations, at=None,
               max_examples=20, haul_fn=None):
    """Pure data-level estimator; each selected row has real contract/order IDs."""
    at = at or datetime.now(timezone.utc)
    candidates, counts = _contract_candidate_rows(
        contracts,items,locations=locations,catalog=catalog,at=at)
    # Prefer genuinely priced multi-item examples instead of the largest
    # arbitrary bundles, which often have zero Jita bids for every item.
    quote_ids = {_int(r.get("type_id")) for r in market
                 if _int(r.get("location_id")) == JITA
                 and _true(r.get("is_buy_order"))
                 and (_float(r.get("volume_remain")) or 0) > 0}
    quote_ids.discard(None)
    candidates.sort(key=lambda c:(
        not c["contains_approved_plex_crate"],
        -len(set(c["goods"]) & quote_ids),
        c["source_location"] != JITA, -len(c["goods"]), c["contract_id"]))
    test_set = candidates[:MAX_AUDIT_CANDIDATES]
    # Crate conversion has an implicit PLEX exit that is not listed in the
    # contract items. Always load the actual Jita PLEX bid book.
    used_types = {tid for c in test_set for tid in c["goods"]} | {PLEX}
    bids = [
        r for r in market if
        _int(r.get("type_id")) in used_types
        and _int(r.get("location_id")) == JITA
        and _true(r.get("is_buy_order"))
        and (_float(r.get("volume_remain")) or 0) > 0
    ]
    books = _books(_orders(bids))
    checked = []
    for c in test_set:
        goods = c["goods"]
        boxes = {tid:q for tid,q in goods.items() if tid in BOXES}
        other = {tid:q for tid,q in goods.items() if tid not in boxes}
        model = _cash_out(boxes,other,books)
        independent_plex_units = sum(BOXES[t][1]*q for t,q in boxes.items())
        independent_plex_units += other.get(PLEX,0)
        breakdown = []
        uncredited = []
        total = 0.
        independent_missing_plex = False
        if independent_plex_units:
            match = _manual_match(books.get((JITA,PLEX,True),[]),
                                  independent_plex_units)
            if match["matched_units"] != independent_plex_units:
                independent_missing_plex = True
            total += match["gross_isk"]
            breakdown.append({"type_id":PLEX,"kind":"PLEX_CONVERTED",
                              "requested_units":independent_plex_units,**match})
        random_total = sum(q*15_000_000 for t,q in boxes.items() if BOXES[t][1] == 0)
        total += random_total
        for tid,qty in other.items():
            if tid == PLEX:
                continue
            match = _manual_match(books.get((JITA,tid,True),[]),qty)
            total += match["gross_isk"]
            if match["remaining_units_unpriced"]:
                uncredited.append(tid)
            breakdown.append({"type_id":tid,"kind":"REAL_INCLUDED_ITEM",
                              "requested_units":qty,**match})
        if independent_missing_plex:
            if model is not None:
                raise RuntimeError("REAL_MIXED_CONTRACT_PLEX_DEPTH_MISMATCH")
            classification = "PLEX_NO_FULL_JITA_BID_DEPTH"
            model_gross = None
            verified = True
        else:
            if model is None or not math.isclose(
                total,model["gross"],rel_tol=1e-11,abs_tol=.01):
                raise RuntimeError(
                    "REAL_MIXED_CONTRACT_INDEPENDENT_JITA_BUY_DEPTH_MISMATCH")
            classification = "INDEPENDENT_JITA_BID_DEPTH_AGREES"
            model_gross = model["gross"]
            verified = True
        unit_volumes = {}
        cargo_volume = 0.
        unknown_volumes = []
        for tid,qty in goods.items():
            vol = _float(catalog.volume(tid))
            if vol is None or vol <= 0:
                unknown_volumes.append(tid)
                continue
            # Only count credited ordinary items; box units always count.
            if tid in boxes:
                n = qty
            elif tid == PLEX:
                n = qty
            else:
                n = next((d["matched_units"] for d in breakdown
                          if d["type_id"] == tid),0)
            unit_volumes[str(tid)] = vol
            cargo_volume += n * vol
        freight = None
        if not unknown_volumes and haul_fn is not None:
            freight = _float(haul_fn(c["source_location"],cargo_volume))
        gross = total if not independent_missing_plex else None
        profit = ((gross*(1-TAX)-c["contract_price_isk"])
                  if gross is not None else None)
        checked.append({
            "contract_id":c["contract_id"],"source_location":c["source_location"],
            "actual_contract_price_isk":c["contract_price_isk"],
            "actual_included_types":len(goods),
            "included_types_with_jita_bids":len(set(goods) & quote_ids),
            "included_item_quantities":{str(t):q for t,q in goods.items()},
            "contains_approved_plex_crate":c["contains_approved_plex_crate"],
            "reference_valuation_classification":classification,
            "independent_cross_check_passed":verified,
            "gross_jita_buy_depth_isk":gross,
            "model_gross_jita_buy_depth_isk":model_gross,
            "tax_rate":TAX,
            "net_before_haul_isk":profit,
            "cargo_volume_for_credited_units_m3":cargo_volume,
            "unknown_volume_types":unknown_volumes[:12],
            "haul_estimate_isk":freight,
            "net_after_haul_isk":(profit-freight if profit is not None and freight is not None else None),
            "unmatched_item_type_ids":uncredited,
            "itemized_actual_jita_order_fills":breakdown,
            "random_crate_user_assumption_isk":random_total,
        })
    checked.sort(key=lambda r:(
        not r["contains_approved_plex_crate"],
        -sum(d["gross_isk"] for d in r["itemized_actual_jita_order_fills"]),
        r["contract_id"]))
    examples = checked[:max_examples]
    real_crate_mixed = sum(x["contains_approved_plex_crate"] for x in candidates)
    return {
        "status":"HISTORICAL_REAL_MULTI_ITEM_CONTRACT_DEPTH_AUDIT",
        "contract_source_scope": "PUBLIC_ITEM_EXCHANGE_APPROVED_LOCATIONS",
        "selection_counts":dict(counts),
        "real_plex_crate_plus_other_contract_candidates": real_crate_mixed,
        "actual_contracts_cross_checked":len(checked),
        "real_mixed_contracts_with_any_jita_buy_bid":sum(
            bool(set(c["goods"]) & quote_ids) for c in candidates),
        "sampled_contracts_with_two_plus_priced_item_types":sum(
            x["included_types_with_jita_bids"] >= 2 for x in checked),
        "examples":examples,
        "all_cross_checks_passed":bool(checked) and all(
            x["independent_cross_check_passed"] for x in checked),
        "basis":"Real contract item quantities + actual Jita buy order IDs, matched depth, one contract price; historical nonlive",
        "limitations":[
            "No live buyer/order/contract access verification; not an executable trade.",
            "Estimated tax fixed to 3.375%, user profile not live verified.",
            "The absence of mixed PLEX crate contracts does not equal validation of that special case.",
            "Missing Jita quotes are valued at zero; partial depth is credited only for matched units.",
            "Freight and blueprint state are separately gated; no invented zero freight.",
            "Maximum first 350 eligible contracts independently checked, 20 displayed."
        ],
    }


def run(data_root, run_name, *, max_examples=20):
    root = Path(data_root).resolve()
    if not run_name or Path(run_name).name != run_name or "/" in run_name or "\\" in run_name:
        raise ValueError("REAL_MULTI_AUDIT_RUN_NAME_INVALID")
    folder = (root/"runs"/run_name).resolve()
    if folder.parent != (root/"runs").resolve():
        raise ValueError("REAL_MULTI_AUDIT_RUN_OUT_OF_SCOPE")
    manifest = json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("status")!="SHADOW_RECORDED"
            or manifest.get("source_input_integrity")!="ALL_PARSED"
            or manifest.get("failed_structure_lanes")):
        raise RuntimeError("REAL_MULTI_AUDIT_SOURCE_NOT_COMPLETE")
    health = manifest.get("structure_health") or {}
    if set(health) != set(STRUCTURES) or any(
            x.get("status")!="COMPLETE" for x in health.values()):
        raise RuntimeError("REAL_MULTI_AUDIT_STRUCTURE_INCOMPLETE")
    at = _time(manifest.get("finished_at"))
    if at is None:
        raise RuntimeError("REAL_MULTI_AUDIT_TIMESTAMP_MISSING")
    locations = {JITA,60008494,60011866} | {
        int(x["location"]) for x in health.values() if x.get("location")}
    npc = load_catalog(root) or {}
    npc_stations={int(k):v for k,v in (npc.get("stations") or {}).items()}
    locations.update(npc_stations)
    catalog = Catalog.load(DEFAULT_CACHE)
    contract_df, item_df = contract_dataframes(folder/"source"/"public_contracts.tar.bz2")
    contract_df = contract_df[contract_df["start_location_id"].isin(locations)]
    item_df = item_df[item_df["contract_id"].isin(set(contract_df["contract_id"]))]
    # Do NOT truncate any contract included-item data before grouping.
    contracts=contract_df.to_dict("records")
    items=item_df.to_dict("records")
    market=market_dataframe(folder/"source"/"market_orders.csv.bz2")
    # First narrow by Jita buy side. Pure pandas prefilter, not a new snapshot.
    market=market[(market["location_id"]==JITA) &
                  market["is_buy_order"].astype(str).str.lower().isin(("true","1","t"))]
    def freight(loc, volume):
        return haul(loc,JITA,volume,{},npc_stations)
    report=audit_rows(contracts,items,market.to_dict("records"),
                      catalog=catalog,locations=locations,at=at,
                      haul_fn=freight,max_examples=max_examples)
    report["source_run"]=run_name
    report["as_of_source_finished_at"]=manifest["finished_at"]
    report["source_public_contract_count"]=len(contracts)
    report["source_public_included_item_row_count"]=len(items)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    p.add_argument("--run",required=True)
    p.add_argument("--max-examples",type=int,default=20)
    a=p.parse_args()
    if not 1<=a.max_examples<=50:
        p.error("--max-examples requires 1..50")
    print(json.dumps(run(a.data_root,a.run,max_examples=a.max_examples),
                     ensure_ascii=False,indent=2,allow_nan=False))


if __name__=="__main__":
    main()
