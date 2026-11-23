"""Why did crate radar find zero profitable contracts? Offline, reproducible.

Reads ONE named V4 run's existing market/contract archives. No Worker, ESI,
mail, SQLite, scheduler or production writes. Counterfactual global PLEX bids
are for diagnosis only and may include inaccessible structure orders.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path

from v4.celebration_crate_radar import (
    BOXES, PLEX, JITA, TAX, _cash_out, _books, _orders, _source_rows, _time,
)
from v4.catalog import Catalog, DEFAULT_CACHE

GLOBAL_PLEX_REGION = 19000001


def integer(x):
    try:
        n = int(x)
        return n if not isinstance(x, bool) else None
    except (ValueError, TypeError, OverflowError):
        return None


def finite(x):
    try:
        n = float(x)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError, OverflowError):
        return None


def included_flag(x):
    return str(x).lower().strip() in ("true", "t", "1")


def order_is_bid(row):
    return included_flag(row.get("is_buy_order"))


def _exit_books(market_rows):
    orders = _orders(market_rows)
    jita = _books(orders)
    global_orders = [
        o for o, raw in zip(orders, (r for r in market_rows
                    if finite(r.get("volume_remain")) not in (0, None)))
        if o.type_id == PLEX and o.buy
        and integer(raw.get("region_id")) == GLOBAL_PLEX_REGION
    ]
    # Don't assume that restricted Upwell structure bids are executable.
    global_npc = [o for o in global_orders
                  if 60_000_000 <= o.location_id < 70_000_000]
    npc_books = dict(jita)
    npc_books[(JITA, PLEX, True)] = sorted(global_npc,
                    key=lambda o: (-o.price, o.order_id))
    all_books = dict(jita)
    all_books[(JITA, PLEX, True)] = sorted(global_orders,
                    key=lambda o: (-o.price, o.order_id))
    return jita, npc_books, all_books


def audit_rows(contracts, items, market, *, locations, catalog,
               haul_fn, at=None):
    """Pure function. Returns all crate contracts, including rejected rows."""
    at = at or datetime.now(timezone.utc)
    booked = defaultdict(lambda: defaultdict(int))
    requested = set()
    for row in items:
        cid, tid, qty = (integer(row.get(k)) for k in
                          ("contract_id", "type_id", "quantity"))
        if cid is None or tid is None or qty is None:
            continue
        if not included_flag(row.get("is_included")):
            requested.add(cid)
        elif qty > 0:
            booked[cid][tid] += qty

    books, npc_books, all_books = _exit_books(market)
    output = []
    reasons = Counter()
    for c in contracts:
        cid = integer(c.get("contract_id"))
        loc = integer(c.get("start_location_id"))
        if cid is None or loc not in locations:
            continue
        goods = booked[cid]
        boxes = {tid: q for tid, q in goods.items() if tid in BOXES and q > 0}
        if not boxes:
            continue
        price = finite(c.get("price"))
        expire_raw = c.get("date_expired")
        expires = _time(expire_raw)
        # np.nan is truthy: the scanner's current exact branch will reject
        # malformed/NaN date_expired if that field is present. Count explicitly.
        bad_expiry = expire_raw is not None and str(expire_raw).strip() not in ("", "None") and expires is None
        reason = None
        if cid in requested:
            reason = "CONTRACT_REQUESTS_ITEMS"
        elif str(c.get("type", "")).lower() != "item_exchange":
            reason = "NOT_ITEM_EXCHANGE"
        elif str(c.get("status", "outstanding")).lower() not in ("outstanding", ""):
            reason = "NOT_OUTSTANDING"
        elif bad_expiry:
            reason = "UNPARSEABLE_EXPIRY_SCANNER_REJECTS"
        elif expires is not None and expires < at:
            reason = "EXPIRED_AT_SOURCE_SNAPSHOT"
        elif price is None or price < 0:
            reason = "CONTRACT_PRICE_INVALID"
        record = {
            "contract_id": cid, "source_location": loc,
            "price_isk": price, "box_types": {str(k): q for k,q in boxes.items()},
            "guaranteed_plex": sum(BOXES[t][1]*q for t,q in boxes.items()),
            "expiry": str(expire_raw)[:32] if expire_raw is not None else None,
            "expiry_parsed": expires is not None,
            "other_type_count": len(goods)-len(boxes),
            "rejection": reason,
        }
        if reason is not None:
            reasons[reason] += 1
            output.append(record)
            continue

        other = {tid: q for tid,q in goods.items()
                 if tid not in boxes and catalog.classification(tid) != "blueprint_type"}
        reference = _cash_out(boxes, other, books)
        npc_case = _cash_out(boxes, other, npc_books)
        global_case = _cash_out(boxes, other, all_books)
        if reference is None:
            record["rejection"] = "JITA_PLEX_BID_DEPTH_MISSING"
            reasons[record["rejection"]] += 1
            output.append(record)
            continue

        # Same credited subset as the scanner; skip unpriced goods for haul.
        cargo = dict(boxes)
        for tid in other:
            matched = reference["other_matched_units"].get(str(tid),0)
            if matched:
                cargo[tid] = matched
        volume = 0.0
        unknown_volume = []
        for tid,qty in cargo.items():
            unit = finite(catalog.volume(tid))
            if unit is None or unit <= 0:
                unknown_volume.append(tid)
                continue
            volume += unit*qty
        freight = None if unknown_volume else finite(haul_fn(loc, volume))
        before_haul = reference["net_after_tax"] - price
        post_haul = before_haul - freight if freight is not None else None
        record.update({
            "other_items_jita_matched": reference["other_exit_breakdown"][:10],
            "other_missing_buy_types": reference["unpriced_other_types"][:15],
            "gross_jita_isk": reference["gross"],
            "net_before_haul_jita_isk": before_haul,
            "estimated_haul_isk": freight,
            "net_after_haul_jita_isk": post_haul,
            "net_before_haul_global_npc_isk": (npc_case["net_after_tax"]-price
                  if npc_case else None),
            "net_before_haul_global_all_isk": (global_case["net_after_tax"]-price
                  if global_case else None),
            "global_npc_vs_jita_gain_before_haul_isk": (
                  npc_case["net_after_tax"]-reference["net_after_tax"]
                  if npc_case else None),
            "missing_volume_type_ids": unknown_volume[:10],
            "expiry_status_at_snapshot": "VALID_OR_ABSENT",
        })
        if before_haul <= 0:
            reason = "LOSS_EVEN_BEFORE_HAUL"
        elif unknown_volume:
            reason = "CARGO_VOLUME_MISSING"
        elif freight is None:
            reason = "HAUL_UNVERIFIED"
        elif post_haul <= 0:
            reason = "HAUL_ELIMINATES_PROFIT"
        else:
            reason = "POSITIVE_JITA_RESEARCH_ESTIMATE_CHECK_SCANNER_FILTER"
        record["rejection"] = reason
        reasons[reason] += 1
        output.append(record)
    output.sort(key=lambda row: (
        0 if row["rejection"] == "POSITIVE_JITA_RESEARCH_ESTIMATE_CHECK_SCANNER_FILTER" else 1,
        -(row.get("net_before_haul_jita_isk") or -1e30), row["contract_id"]))
    return {
        "contracts_with_included_target_crate_in_locations": len(output),
        "reason_counts": dict(reasons),
        "contracts": output,
        "notes": [
            "Jita scenario reproduces PLEX station-location buy-depth pricing of approved radar.",
            "Global NPC and Global all are counterfactuals, not authorized valuation.",
            "Private-structure PLEX buy orders may not be executable without ACL access.",
            "Partial matched ordinary goods credited at real Jita bid-depth; unmatched units zero.",
            "Haul uses existing V4 static heuristic with no ESI route query; unknown route is not zero.",
            "This is a source-snapshot retrospective, not live order/contract revalidation."
        ],
    }


def run(root, run_name):
    from v4.npc_station_catalog import load_catalog
    from v4.deep_scan import haul
    root = Path(root).resolve()
    if (not run_name or Path(run_name).name != run_name
            or "\\" in run_name or "/" in run_name):
        raise ValueError("CRATE_CONTRACT_AUDIT_RUN_NAME_INVALID")
    folder = (root / "runs" / run_name).resolve()
    if folder.parent != (root / "runs").resolve():
        raise ValueError("CRATE_CONTRACT_AUDIT_RUN_OUTSIDE_ROOT")
    manifest = json.loads((folder / "manifest.json").read_text("utf-8"))
    if (manifest.get("status") != "SHADOW_RECORDED"
            or manifest.get("source_input_integrity") != "ALL_PARSED"
            or manifest.get("failed_structure_lanes")):
        raise RuntimeError("CRATE_CONTRACT_AUDIT_SOURCE_INCOMPLETE")
    structure = manifest.get("structure_health") or {}
    if not structure or any(v.get("status") != "COMPLETE" for v in structure.values()):
        raise RuntimeError("CRATE_CONTRACT_AUDIT_STRUCTURE_INCOMPLETE")
    at = _time(manifest.get("finished_at"))
    if at is None:
        raise RuntimeError("CRATE_CONTRACT_AUDIT_MISSING_SNAPSHOT_TIMESTAMP")
    npc = load_catalog(root) or {}
    npc_stations = {int(k):v for k,v in (npc.get("stations") or {}).items()}
    locations = {JITA, 60008494, 60011866} | set(npc_stations)
    locations |= {int(s["location"]) for s in structure.values()
                  if s.get("status") == "COMPLETE" and s.get("location")}
    if len(locations) < 3:
        raise RuntimeError("CRATE_CONTRACT_AUDIT_SCOPE_INVALID")
    contracts, items, public, _ = _source_rows(folder, locations)
    catalog = Catalog.load(DEFAULT_CACHE)
    def freight(loc,volume):
        # Empty metadata deliberately prevents NPC hub-to-Jita route ESI calls.
        return haul(loc, JITA, volume, {}, npc_stations)
    result = audit_rows(contracts,items,public,locations=locations,
                        catalog=catalog,haul_fn=freight,at=at)
    result.update({"status":"OFFLINE_CONTRACT_ZERO_RESULT_DIAGNOSTIC",
                   "source_run":run_name,
                   "snapshot_finished_at":manifest.get("finished_at"),
                   "global_plex_region": GLOBAL_PLEX_REGION,
                   "side_effects":False})
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    p.add_argument("--run",required=True)
    a = p.parse_args()
    print(json.dumps(run(a.data_root,a.run),ensure_ascii=False,indent=2,allow_nan=False))


if __name__ == "__main__":
    main()
