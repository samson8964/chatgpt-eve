"""Read-only retrospective diagnosis of a zero-result PLEX celebration crate scan.

Never touches ESI, Worker, email, SQLite, schedule, production code or backup.
Accepts an exact existing V4 run folder; never silently switches run dates.
Shows whether GLOBAL PLEX MARKET region 19000001 exists in the source archive
and whether Jita-only (60003760) PLEX buy orders have different coverage.
This tool does not change an approved valuation basis.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from v4.celebration_crate_radar import BOXES, JITA, PLEX, TAX, RANDOM_ISK
from v4.sources import market_dataframe, contract_dataframes

GLOBAL_PLEX_REGION = 19000001
MARKET_LOCATIONS = {60003760, 60008494, 60011866}
FILLABLE_BUY = {"true", "1", "t"}
ORDER_ACTIVE = {"outstanding", ""}


def _int(x):
    try:
        return int(x)
    except (TypeError, ValueError, OverflowError):
        return None


def _time(x):
    if x is None or not str(x).strip() or str(x) == "nan":
        return None
    try:
        t = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _is_true(x):
    return str(x).strip().lower() in FILLABLE_BUY


def _int_counter(df, col):
    count = Counter()
    if col not in df.columns:
        return {}
    for x in df[col]:
        k = _int(x)
        if k is not None:
            count[str(k)] += 1
    return dict(sorted(count.items(), key=lambda a: (-a[1], a[0])))


def analyze(market, contracts, items, *, structure_ids=(), npc_ids=(),
            at=None):
    """Pure pandas diagnostic. Never equate zero offers to zero full-scan access."""
    at = at or datetime.now(timezone.utc)
    needed_market = {"type_id","region_id","location_id","is_buy_order",
                     "price","volume_remain","order_id"}
    needed_contract = {"contract_id","start_location_id","price","type"}
    needed_items = {"contract_id","type_id","quantity","is_included"}
    if needed_market - set(market.columns):
        raise RuntimeError("CRATE_AUDIT_MARKET_REGION_OR_FIELDS_MISSING")
    if needed_contract - set(contracts.columns):
        raise RuntimeError("CRATE_AUDIT_CONTRACT_FIELDS_MISSING")
    if needed_items - set(items.columns):
        raise RuntimeError("CRATE_AUDIT_CONTRACT_ITEM_FIELDS_MISSING")
    import pandas as pd
    structure_ids = {int(v) for v in structure_ids}
    market_locs = MARKET_LOCATIONS | structure_ids
    contract_locs = market_locs | {int(v) for v in npc_ids}
    mm = market[market["type_id"].isin(set(BOXES) | {PLEX})].copy()
    mm["_buy"] = mm["is_buy_order"].map(_is_true)
    mm["_loc"] = pd.to_numeric(mm["location_id"], errors="coerce")
    mm["_region"] = pd.to_numeric(mm["region_id"], errors="coerce")
    mm["_price"] = pd.to_numeric(mm["price"], errors="coerce")
    mm["_remaining"] = pd.to_numeric(mm["volume_remain"], errors="coerce")
    live = mm[(mm["_remaining"] > 0) & (mm["_price"] > 0)]
    plex_bids = live[(live["type_id"] == PLEX) & live["_buy"]]
    global_bids = plex_bids[plex_bids["_region"] == GLOBAL_PLEX_REGION]
    jita_bids = plex_bids[plex_bids["_loc"] == JITA]
    other_bids = plex_bids[(plex_bids["_loc"] != JITA)
                           & (plex_bids["_region"] != GLOBAL_PLEX_REGION)]
    def summary(frame):
        if frame.empty:
            return {"orders": 0, "units": 0, "best_bid_isk": None}
        return {"orders": int(len(frame)),
                "units": int(frame["_remaining"].sum()),
                "best_bid_isk": float(frame["_price"].max())}
    plex = {
        "global_region_id": GLOBAL_PLEX_REGION,
        "global_market_bids": summary(global_bids),
        "jita_location_bids": summary(jita_bids),
        "other_non_global_bids": summary(other_bids),
        "all_snapshot_plex_bids": summary(plex_bids),
        "plex_region_distribution": _int_counter(plex_bids, "_region"),
        "plex_location_distribution_top10": dict(
            list(_int_counter(plex_bids, "_loc").items())[:10]),
        "global_and_jita_order_id_overlap": int(len(
            set(global_bids["order_id"]) & set(jita_bids["order_id"]))),
        "interpretation": (
            "GLOBAL_REGION_PRESENT_JITA_ONLY_BASIS_MAY_UNDERVALUE"
            if len(global_bids) and len(jita_bids) < len(global_bids)
            else "GLOBAL_REGION_NOT_IN_SNAPSHOT_VERIFY_ESI_19000001"
            if not len(global_bids)
            else "JITA_AND_GLOBAL_OVERLAP_CHECK_LOCATIONS"
        ),
    }
    sells = live[(live["type_id"].isin(BOXES)) & ~live["_buy"]]
    eligible = sells[sells["_loc"].isin(market_locs)]
    global_top = summary(global_bids)["best_bid_isk"]
    jita_top = summary(jita_bids)["best_bid_isk"]
    boxes = {}
    for tid, (name, guaranteed) in BOXES.items():
        all_sales = sells[sells["type_id"] == tid]
        in_scope = eligible[eligible["type_id"] == tid]
        best_ask = float(in_scope["_price"].min()) if not in_scope.empty else None
        per_box_global = (guaranteed * global_top if guaranteed and global_top is not None
                          else RANDOM_ISK if not guaranteed else None)
        per_box_jita = (guaranteed * jita_top if guaranteed and jita_top is not None
                        else RANDOM_ISK if not guaranteed else None)
        boxes[str(tid)] = {
            "name": name, "fixed_plex_each": guaranteed,
            "all_public_market_sell_orders": int(len(all_sales)),
            "in_scope_public_market_sell_orders": int(len(in_scope)),
            "in_scope_public_market_sell_units": int(in_scope["_remaining"].sum()),
            "best_scope_ask_isk": best_ask,
            "optimistic_one_box_before_haul_global_isk":
                (per_box_global * (1 - TAX) - best_ask)
                if per_box_global is not None and best_ask is not None else None,
            "optimistic_one_box_before_haul_jita_isk":
                (per_box_jita * (1 - TAX) - best_ask)
                if per_box_jita is not None and best_ask is not None else None,
        }
    ii = items[items["type_id"].isin(BOXES)].copy()
    ii["_included"] = ii["is_included"].map(_is_true)
    crate_rows = ii[ii["_included"]]
    scoped_contracts = contracts[contracts["start_location_id"].isin(contract_locs)].copy()
    all_ids = set(crate_rows["contract_id"].dropna())
    in_scope_contract_ids = set(scoped_contracts["contract_id"].dropna())
    in_scope_crate_ids = all_ids & in_scope_contract_ids
    relevant = scoped_contracts[scoped_contracts["contract_id"].isin(in_scope_crate_ids)].copy()
    req_ids = set(items.loc[
        ~items["is_included"].map(_is_true), "contract_id"].dropna())
    is_item_exchange = relevant["type"].astype(str).str.lower().eq("item_exchange")
    if "status" in relevant.columns:
        status_text = relevant["status"].astype(str).str.lower()
        is_current = status_text.isin(ORDER_ACTIVE)
        status_counts = dict(Counter(status_text))
    else:
        is_current = pd.Series([True] * len(relevant), index=relevant.index)
        status_counts = {"COLUMN_MISSING": len(relevant)}
    price = pd.to_numeric(relevant["price"],errors="coerce")
    with_valid_price = price.notna() & (price >= 0)
    if "date_expired" in relevant.columns:
        expired = relevant["date_expired"].map(
            lambda x: _time(x) is not None and _time(x) < at)
    else:
        expired = pd.Series([False] * len(relevant), index=relevant.index)
    requested = relevant["contract_id"].isin(req_ids)
    base_valid = is_item_exchange & is_current & with_valid_price & ~expired & ~requested
    box_type_contracts = {}
    for tid, (name, guaranteed) in BOXES.items():
        type_cids = set(crate_rows.loc[
            crate_rows["type_id"] == tid, "contract_id"].dropna())
        box_type_contracts[str(tid)] = len(type_cids & in_scope_crate_ids)
    return {
        "snapshot_market_total_rows": int(len(market)),
        "snapshot_contract_total_rows": int(len(contracts)),
        "snapshot_contract_item_total_rows": int(len(items)),
        "plex": plex,
        "listed_boxes": boxes,
        "public_market_crate_sell_orders_all": int(len(sells)),
        "public_market_crate_sell_orders_in_scope": int(len(eligible)),
        "private_structure_market_offers": "NOT_STORED_IN_V4_PUBLIC_SNAPSHOT",
        "contracts": {
            "crate_included_contract_ids_global": len(all_ids),
            "crate_included_contract_ids_in_scope": len(in_scope_crate_ids),
            "excluded_by_requested_items_in_scope": int(requested.sum()),
            "item_exchange_in_scope": int(is_item_exchange.sum()),
            "non_item_exchange_in_scope": int((~is_item_exchange).sum()),
            "status_distribution_in_scope": status_counts,
            "non_outstanding_in_scope": int((~is_current).sum()),
            "invalid_price_in_scope": int((~with_valid_price).sum()),
            "expired_at_snapshot_time": int(expired.sum()),
            "potentially_eligible_before_plex_and_freight": int(base_valid.sum()),
            "included_crate_contracts_by_type": box_type_contracts,
        },
        "status": "RETROSPECTIVE_SOURCE_DIAGNOSTIC_NO_REALTIME_CLAIMS",
        "notes": [
            "Existing scanner uses only Jita location PLEX bids, not global region 19000001.",
            "One-box optimistic spread is BEFORE freight, order-depth and any access validation.",
            "Private-structure orders were fetched for V4 proof but are not stored in public source archive.",
            "This report does not change the approved price basis or produce/signal trades."
        ],
    }


def run(root, run_name):
    root = Path(root).resolve()
    if (not run_name or Path(run_name).name != run_name
            or "/" in run_name or "\\" in run_name):
        raise ValueError("CRATE_AUDIT_RUN_NAME_INVALID")
    folder = (root / "runs" / run_name).resolve()
    if folder.parent != (root / "runs").resolve():
        raise ValueError("CRATE_AUDIT_RUN_OUTSIDE_ROOT")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("status") != "SHADOW_RECORDED"
            or manifest.get("source_input_integrity") != "ALL_PARSED"
            or manifest.get("failed_structure_lanes")):
        raise RuntimeError("CRATE_AUDIT_SOURCE_NOT_COMPLETE")
    deep = json.loads((folder / "deep_shadow.json").read_text(encoding="utf-8"))
    structure_health = deep.get("structure_health") or {}
    if not structure_health or any(x.get("status") != "COMPLETE"
                                   for x in structure_health.values()):
        raise RuntimeError("CRATE_AUDIT_STRUCTURE_COVERAGE_NOT_COMPLETE")
    market = market_dataframe(folder / "source" / "market_orders.csv.bz2")
    contracts, items = contract_dataframes(folder / "source" / "public_contracts.tar.bz2")
    from v4.npc_station_catalog import load_catalog
    npc = load_catalog(root) or {}
    npc_ids = [int(x) for x in (npc.get("stations") or {})]
    at = _time(manifest.get("finished_at"))
    if at is None:
        raise RuntimeError("CRATE_AUDIT_SNAPSHOT_TIMESTAMP_MISSING")
    report = analyze(
        market, contracts, items,
        structure_ids=(v.get("location") for v in structure_health.values()),
        npc_ids=npc_ids, at=at)
    report["source_run"] = run_name
    report["snapshot_finished_at"] = manifest["finished_at"]
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-root", type=Path, default=Path.home() / "EVE-V4-Data")
    p.add_argument("--run", required=True, help="Exact existing V4 run folder name")
    args = p.parse_args()
    print(json.dumps(run(args.data_root, args.run), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
