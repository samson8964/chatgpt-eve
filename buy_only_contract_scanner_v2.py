from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

import buy_only_contract_scanner as legacy
from contract_deal_scanner import (
    SALES_TAX_RATE,
    current_friendly_alliances,
    haul_reserve,
    load_structures,
    resolve_location,
    sovereignty_owners,
)
from opportunity_engine_v2 import (
    aggregate_market_executable_items,
    analyze_contract_items,
    bundle_liquidity,
    classify_execution_status,
    estimate_transport,
    fetch_jita_history,
    fetch_live_jita_buy_books,
    liquidate_bundle,
    opportunity_score,
    score_grade,
    snapshot_change_pct,
    walk_book,
)
from scanner_source import (
    DATA,
    LATEST,
    MARKET_ORDERS_INDEX,
    PUBLIC_CONTRACTS_INDEX,
    download,
    fetch_many_ref,
    latest_file,
    load_contracts,
    load_market_orders,
    name_en,
    prepare_jita_books,
    truthy_series,
    type_group_id,
    type_volume,
)

LIVE_LIMIT = int(os.getenv("V2_LIVE_REVALIDATE_LIMIT", "120"))
HISTORY_LIMIT = int(os.getenv("V2_HISTORY_CANDIDATE_LIMIT", "60"))


def _snapshot_rig_value(excluded, books):
    return sum(walk_book(books.get(int(tid), []), int(qty)).value for tid, qty in excluded.items())


def _metadata(type_ids):
    types = fetch_many_ref("types", type_ids)
    gids = {type_group_id(v) for v in types.values()}
    gids.discard(None)
    return types, fetch_many_ref("groups", gids)


def _prefilter_market_executable_groups(df):
    """Remove non-ship singleton instances before snapshot ranking.

    Only singleton type metadata is needed here. Non-singleton rows remain
    unchanged, while unknown singleton types fail closed and contribute zero.
    """
    if df.empty:
        return {}, {}
    singleton_tids = set()
    for row in df.to_dict("records"):
        raw = row.get("is_singleton", row.get("singleton", False))
        if str(raw or "").strip().lower() in {"1", "true", "t", "yes", "y"}:
            tid = int(row.get("type_id") or 0)
            if tid > 0:
                singleton_tids.add(tid)
    singleton_types, singleton_groups = _metadata(singleton_tids) if singleton_tids else ({}, {})
    grouped = {}
    excluded = {}
    for cid, g in df.groupby("contract_id", sort=False):
        rows = g.to_dict("records")
        q, ex = aggregate_market_executable_items(rows, singleton_types, singleton_groups)
        if q:
            grouped[int(cid)] = q
        if ex:
            excluded[int(cid)] = ex
    return grouped, excluded


def _resolve_locations(candidates):
    friendly, aid, aname, aticker = current_friendly_alliances()
    sov = sovereignty_owners()
    lids = sorted({int(x["start_location_id"]) for x in candidates})
    structures = load_structures([x for x in lids if x >= 1_000_000_000_000])
    out = {}
    with ThreadPoolExecutor(max_workers=min(legacy.LOCATION_WORKERS, max(1, len(lids)))) as ex:
        futs = {ex.submit(resolve_location, lid, structures, friendly, sov): lid for lid in lids}
        for fut in as_completed(futs):
            lid = futs[fut]
            try:
                out[lid] = fut.result()
            except Exception:
                out[lid] = None
    return out, aid, aname, aticker


def main():
    print("Opportunity Engine V2: public-contract discovery")
    c_url, c_modified = latest_file(PUBLIC_CONTRACTS_INDEX)
    m_url, m_modified = latest_file(MARKET_ORDERS_INDEX)
    c_path, m_path = DATA / Path(c_url).name, DATA / Path(m_url).name
    if not c_path.exists():
        download(c_url, c_path)
    if not m_path.exists():
        download(m_url, m_path)

    contracts, items = load_contracts(c_path)
    contracts["contract_id"] = pd.to_numeric(contracts["contract_id"], errors="coerce").astype("Int64")
    contracts["price"] = pd.to_numeric(contracts["price"], errors="coerce").fillna(0.0)
    contracts["start_location_id"] = pd.to_numeric(contracts["start_location_id"], errors="coerce").astype("Int64")
    c = contracts[
        (contracts["type"] == "item_exchange")
        & (contracts["price"] >= legacy.MIN_CONTRACT_PRICE)
        & (contracts["price"] <= legacy.MAX_CONTRACT_PRICE)
        & contracts["start_location_id"].notna()
    ].copy()
    if "date_expired" in c.columns:
        exp = pd.to_datetime(c["date_expired"], utc=True, errors="coerce")
        c = c[exp.isna() | (exp > pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=legacy.MIN_HOURS_TO_EXPIRE))]

    valid = set(c["contract_id"].dropna().astype(int))
    ii = items[items["contract_id"].isin(valid)].copy()
    ii["contract_id"] = pd.to_numeric(ii["contract_id"], errors="coerce").astype("Int64")
    ii["_included"] = truthy_series(ii["is_included"])
    ii["_bpc"] = truthy_series(ii["is_blueprint_copy"])
    ii["quantity"] = pd.to_numeric(ii["quantity"], errors="coerce").fillna(0).astype(int)
    ii["type_id"] = pd.to_numeric(ii["type_id"], errors="coerce").fillna(0).astype(int)
    requested = set(ii.loc[~ii["_included"], "contract_id"].dropna().astype(int))
    bpcs = set(ii.loc[ii["_included"] & ii["_bpc"], "contract_id"].dropna().astype(int))
    usable = valid - requested - bpcs
    inc = ii[ii["contract_id"].isin(usable) & ii["_included"] & (ii["quantity"] > 0) & (ii["type_id"] > 0)]
    raw_groups = {int(cid): g.to_dict("records") for cid, g in inc.groupby("contract_id", sort=False)}
    grouped, early_singletons = _prefilter_market_executable_groups(inc)
    early_singleton_qty = sum(sum(x.values()) for x in early_singletons.values())
    print(
        f"V2 market-ineligible singleton prefilter: contracts={len(early_singletons)} "
        f"qty={early_singleton_qty}"
    )
    c = c[c["contract_id"].isin(grouped)]
    if c.empty:
        legacy.empty_outputs()
        return
    c_by_id = c.set_index("contract_id", drop=False)

    market = load_market_orders(m_path)
    _, snapshot_books = prepare_jita_books(market)
    del market

    broad = []
    wanted = set()
    for cid, itemq in grouped.items():
        cm = c_by_id.loc[cid]
        if isinstance(cm, pd.DataFrame):
            cm = cm.iloc[0]
        price = legacy.safe_num(cm.get("price"))
        quote = liquidate_bundle(itemq, snapshot_books, SALES_TAX_RATE)
        if quote["net_after_tax"] - price < legacy.MIN_NET_PROFIT * 0.5:
            continue
        broad.append({
            "contract_id": cid,
            "contract_price": price,
            "start_location_id": int(cm["start_location_id"]),
            "date_expired": cm.get("date_expired", ""),
            "title": cm.get("title", ""),
            "snapshot_raw": quote,
        })
        wanted.update(itemq)
        for raw in raw_groups.get(int(cid), []):
            try:
                tid = int(raw.get("type_id") or 0)
            except Exception:
                tid = 0
            if tid > 0:
                wanted.add(tid)

    if not broad:
        legacy.empty_outputs()
        return

    type_objs, group_objs = _metadata(wanted)
    feasible = []
    blocked_capitals = excluded_rig_contracts = singleton_adjusted_contracts = skin_removed = 0
    for p in broad:
        f = analyze_contract_items(raw_groups.get(int(p["contract_id"]), []), type_objs, group_objs)
        if f.has_highsec_restricted_ship:
            blocked_capitals += 1
            continue
        if not f.adjusted_itemq:
            continue
        if f.excluded_rigs:
            excluded_rig_contracts += 1
        if f.excluded_market_singletons:
            singleton_adjusted_contracts += 1
        snap = liquidate_bundle(f.adjusted_itemq, snapshot_books, SALES_TAX_RATE)
        gross = float(snap["gross"] or 0)
        skin_value = sum(float(r["gross"] or 0) for r in snap["rows"] if legacy.is_skin_related(int(r["type_id"]), type_objs, group_objs))
        skin_share = skin_value / gross if gross > 0 else 0.0
        if skin_share >= legacy.SKIN_MAJOR_SHARE:
            skin_removed += 1
            continue
        p.update({
            "itemq": f.adjusted_itemq,
            "feasibility": f,
            "snapshot": snap,
            "skin_value_share": skin_share,
            "excluded_rig_value_snapshot": _snapshot_rig_value(f.excluded_rigs, snapshot_books),
            "excluded_market_singleton_types": len(f.excluded_market_singletons),
            "excluded_market_singleton_qty": sum(f.excluded_market_singletons.values()),
        })
        feasible.append(p)

    locations, own_aid, own_name, own_ticker = _resolve_locations(feasible)
    pre_live = []
    location_removed = structure_removed = 0
    for p in feasible:
        loc = locations.get(int(p["start_location_id"]))
        if not loc or int(legacy.safe_num(loc.get("system_id"), 0)) <= 0 or int(legacy.safe_num(loc.get("shortest_jumps_to_jita"), -1)) < 0:
            location_removed += 1
            continue
        if bool(loc.get("is_player_structure")) and not bool(loc.get("friendly_sov")) and not bool(loc.get("friendly_region")):
            structure_removed += 1
            continue
        total_m3 = sum(max(0.0, type_volume(type_objs.get(int(tid)))) * qty for tid, qty in p["itemq"].items())
        haul = haul_reserve(total_m3, loc)
        snap_profit = float(p["snapshot"]["net_after_tax"] or 0) - haul - p["contract_price"]
        invested = p["contract_price"] + haul
        snap_roi = snap_profit / invested if invested > 0 else 0.0
        if snap_profit < legacy.MIN_NET_PROFIT * 0.7 or snap_roi < legacy.MIN_NET_ROI * 0.7:
            continue
        p.update({"loc": loc, "total_m3": total_m3, "haul": haul, "snapshot_profit": snap_profit, "snapshot_roi": snap_roi})
        pre_live.append(p)

    pre_live.sort(key=lambda x: (x["snapshot_profit"], x["snapshot_roi"]), reverse=True)
    pre_live = pre_live[:LIVE_LIMIT]
    live_type_ids = {tid for p in pre_live for tid in p["itemq"]}
    print(f"V2 live Jita revalidation candidates={len(pre_live)} types={len(live_type_ids)}")
    live_books, failed_types, live_at = fetch_live_jita_buy_books(live_type_ids)

    live = []
    for p in pre_live:
        q = liquidate_bundle(p["itemq"], live_books, SALES_TAX_RATE)
        if not q["complete"]:
            continue
        profit = float(q["net_after_tax"] or 0) - p["haul"] - p["contract_price"]
        invested = p["contract_price"] + p["haul"]
        roi = profit / invested if invested > 0 else 0.0
        if profit < legacy.MIN_NET_PROFIT or roi < legacy.MIN_NET_ROI:
            continue
        stress_profit = float(q["stress_net_after_tax"] or 0) - p["haul"] - p["contract_price"]
        change = snapshot_change_pct(p["snapshot"]["gross"], q["gross"])
        failed_here = sorted(set(p["itemq"]).intersection(failed_types))
        status = classify_execution_status(q["complete"], profit, roi, stress_profit, change, ["live_jita_fetch_failed"] if failed_here else [])
        if status == "DANGER":
            continue
        p.update({"live_quote": q, "profit": profit, "roi": roi, "stress_profit": stress_profit, "change": change, "status": status, "live_at": live_at})
        live.append(p)

    live.sort(key=lambda x: (x["profit"], x["roi"]), reverse=True)
    history_types = {tid for p in live[:HISTORY_LIMIT] for tid in p["itemq"]}
    history, _ = fetch_jita_history(history_types)

    rows = []
    for p in live:
        q = p["live_quote"]
        loc = p["loc"]
        liq = bundle_liquidity(p["itemq"], history)
        transport = estimate_transport(p["total_m3"], int(legacy.safe_num(loc.get("shortest_jumps_to_jita"), 0)), p["profit"])
        density = p["profit"] / p["total_m3"] if p["total_m3"] > 0 else p["profit"]
        max_slip = max((float(r.get("slippage_pct", 0) or 0) for r in q["rows"]), default=0.0)
        score = opportunity_score(p["profit"], p["roi"], density, liq["liquidity_score"], p["stress_profit"], loc.get("risk_rank", 5), transport.hours, p["change"], p["status"])
        contrib = sorted(q["rows"], key=lambda x: float(x.get("gross", 0) or 0), reverse=True)
        item_lines = [f"{name_en(type_objs.get(tid), str(tid))} x{qty}" for tid, qty in p["itemq"].items()]
        top_lines = [f"{name_en(type_objs.get(int(r['type_id'])), str(r['type_id']))} x{int(r['quantity'])}≈{float(r['gross'])/1e6:.1f}M" for r in contrib[:12]]
        gross = float(q["gross"] or 0)
        top1 = float(contrib[0]["gross"] or 0) / gross if gross > 0 and contrib else 0.0
        top3 = sum(float(r["gross"] or 0) for r in contrib[:3]) / gross if gross > 0 else 0.0
        f = p["feasibility"]
        net_value = float(q["net_after_tax"] or 0) - p["haul"]
        row = {
            "engine_version": "Opportunity Engine V2",
            "deal_class": "A V2 实时验证即时买单套利",
            "valuation_basis": "LIVE_JITA_BUY_DEPTH_V2",
            "execution_status": p["status"],
            "score_grade": score_grade(score),
            "deal_score": score,
            "opportunity_score": score,
            "contract_id": p["contract_id"],
            "contract_price": p["contract_price"],
            "item_type_count": len(p["itemq"]),
            "item_total_units": sum(p["itemq"].values()),
            "type_quantities_json": json.dumps(p["itemq"], sort_keys=True, separators=(",", ":")),
            "items": " | ".join(item_lines[:20]),
            "top_value_items": " | ".join(top_lines),
            "jita_buy_gross": gross,
            "sales_tax_if_instant": q["sales_tax"],
            "instant_liquidation_net_value": net_value,
            "haul_reserve": p["haul"],
            "instant_net_profit": p["profit"],
            "instant_net_roi": p["roi"],
            "stress_jita_buy_gross": q["stress_gross"],
            "stress_net_profit": p["stress_profit"],
            "buy_unit_coverage": q["coverage"],
            "buy_filled_units": q["filled_units"],
            "total_units": q["requested_units"],
            "jita_buy_max_slippage_pct": max_slip,
            "snapshot_jita_buy_gross": p["snapshot"]["gross"],
            "snapshot_change_pct": p["change"],
            "live_revalidated_at": p["live_at"],
            "top1_value_share": top1,
            "top3_value_share": top3,
            "skin_value_share": p["skin_value_share"],
            "excluded_rig_types": len(f.excluded_rigs),
            "excluded_rig_qty": sum(f.excluded_rigs.values()),
            "excluded_rig_value_snapshot": p["excluded_rig_value_snapshot"],
            "excluded_market_singleton_types": p["excluded_market_singleton_types"],
            "excluded_market_singleton_qty": p["excluded_market_singleton_qty"],
            "has_assembled_ship": f.has_ship,
            "highsec_restricted_ship": f.has_highsec_restricted_ship,
            "total_m3": p["total_m3"],
            "profit_per_m3": density,
            "liquidity_score": liq["liquidity_score"],
            "liquidity_label": liq["liquidity_label"],
            "estimated_fill_time_days": liq["fill_time_days"],
            "historical_fill_rate_30d": liq["historical_fill_rate_30d"],
            "transport_trips": transport.trips,
            "estimated_execution_hours": transport.hours,
            "estimated_isk_per_hour": transport.isk_per_hour,
            "transport_total_leg_jumps": transport.total_leg_jumps,
            "value_coverage": 1.0,
            "chosen_estimated_value": net_value,
            "chosen_value_gap": p["profit"],
            "chosen_discount": p["profit"] / net_value if net_value > 0 else 0.0,
            "chosen_roi": p["roi"],
            "contract_title": p.get("title", ""),
            "date_expired": p.get("date_expired", ""),
            "contracts_snapshot_modified": c_modified,
            "market_snapshot_modified": m_modified,
            "friendly_alliance_id": own_aid,
            "friendly_alliance_name": own_name,
            "friendly_alliance_ticker": own_ticker,
            "eve_contract_url": f"https://eve-contract-opener.99617224.workers.dev/c/{p['contract_id']}",
            **loc,
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        rank = {"SAFE": 0, "CHANGED": 1}
        df["_rank"] = df["execution_status"].map(rank).fillna(9)
        df.sort_values(["_rank", "opportunity_score", "instant_net_profit"], ascending=[True, False, False], inplace=True)
        df.drop(columns=["_rank"], inplace=True)
    LATEST.mkdir(parents=True, exist_ok=True)
    df.to_csv(legacy.SPOT_ALL, index=False)
    df.head(legacy.TOP).to_csv(legacy.SPOT_RESULT, index=False)
    multi = df[df["item_type_count"] >= 2].copy() if not df.empty else pd.DataFrame()
    if not multi.empty:
        multi.sort_values(["opportunity_score", "chosen_value_gap"], ascending=[False, False], inplace=True)
    multi.to_csv(legacy.MULTI_ALL, index=False)
    multi.head(legacy.MULTI_TOP).to_csv(legacy.MULTI_RESULT, index=False)

    safe_count = int((df["execution_status"] == "SAFE").sum()) if not df.empty else 0
    changed_count = int((df["execution_status"] == "CHANGED").sum()) if not df.empty else 0
    print(
        f"V2 done spot={len(df)} safe={safe_count} changed={changed_count} multi={len(multi)} "
        f"capital_blocked={blocked_capitals} rig_adjusted={excluded_rig_contracts} "
        f"singleton_adjusted={singleton_adjusted_contracts} skin_removed={skin_removed} "
        f"location_removed={location_removed} unknown_structure_removed={structure_removed}"
    )


if __name__ == "__main__":
    main()
