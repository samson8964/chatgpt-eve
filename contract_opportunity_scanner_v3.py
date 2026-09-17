from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

import buy_only_contract_scanner as legacy
from contract_deal_scanner import BROKER_FEE_RATE, RELIST_RESERVE_RATE, SALES_TAX_RATE, current_friendly_alliances, haul_reserve, load_structures, resolve_location, sovereignty_owners
from opportunity_engine_v2 import analyze_contract_items, classify_execution_status, fetch_live_jita_buy_books, liquidate_bundle, safe_float
from opportunity_engine_v3 import cash_floor_bundle, conservative_sell_bundle, fetch_jita_price_history, fetch_live_jita_sell_books, procure_bundle, select_candidate_union
from scanner_source import DATA, LATEST, MARKET_ORDERS_INDEX, PUBLIC_CONTRACTS_INDEX, download, fetch_many_ref, latest_file, load_contracts, load_market_orders, name_en, prepare_jita_books, truthy_series, type_group_id, type_volume

ENGINE = "Opportunity Engine V3"
LIVE_LIMIT = int(os.getenv("V3_CONTRACT_LIVE_LIMIT", "240"))
PROFIT_QUOTA = int(os.getenv("V3_CONTRACT_PROFIT_QUOTA", "120"))
ROI_QUOTA = int(os.getenv("V3_CONTRACT_ROI_QUOTA", "60"))
RECENT_QUOTA = int(os.getenv("V3_CONTRACT_RECENT_QUOTA", "80"))
SELL_MIN_PROFIT = float(os.getenv("V3_SELL_MIN_NET_PROFIT", "50000000"))
SELL_MIN_ROI = float(os.getenv("V3_SELL_MIN_NET_ROI", "0.15"))
SELL_MAX_FILL_DAYS = float(os.getenv("V3_SELL_MAX_FILL_DAYS", "7"))
SELL_MIN_INCREMENT = float(os.getenv("V3_SELL_MIN_INCREMENTAL_PROFIT", "20000000"))
RESULT = LATEST / "contract_opportunities_v3.csv"
REPORT = LATEST / "contract_opportunities_v3.md"


def _aggregate(df: pd.DataFrame) -> dict[int, int]:
    return legacy.aggregate_items(df)


def _best_ask_gross(itemq: dict[int, int], sell_books: dict[int, list[dict]]) -> float:
    gross = 0.0
    for tid, qty in itemq.items():
        book = sell_books.get(int(tid), [])
        if not book:
            return 0.0
        price = safe_float(book[0].get("price"), 0.0)
        if price <= 0:
            return 0.0
        gross += price * int(qty)
    return gross


def _item_text(itemq: dict[int, int], types: dict[int, dict], limit: int = 12) -> str:
    parts = [f"{name_en(types.get(int(tid)), str(tid))} x{int(qty)}" for tid, qty in itemq.items()]
    return " | ".join(parts[:limit])


def _location_map(candidates):
    friendly, aid, aname, aticker = current_friendly_alliances()
    sov = sovereignty_owners()
    lids = sorted({int(x["start_location_id"]) for x in candidates})
    structures = load_structures([x for x in lids if x >= 1_000_000_000_000])
    out = {}
    for lid in lids:
        out[lid] = resolve_location(lid, structures, friendly, sov)
    return out, aid, aname, aticker


def _fees(gross: float):
    broker = gross * BROKER_FEE_RATE
    tax = gross * SALES_TAX_RATE
    relist = gross * RELIST_RESERVE_RATE
    return broker, tax, relist


def main():
    LATEST.mkdir(parents=True, exist_ok=True)
    print("V3 contracts 1) load public contracts and Jita snapshot")
    c_url, c_modified = latest_file(PUBLIC_CONTRACTS_INDEX)
    m_url, m_modified = latest_file(MARKET_ORDERS_INDEX)
    c_path = DATA / Path(c_url).name
    m_path = DATA / Path(m_url).name
    if not c_path.exists():
        download(c_url, c_path)
    if not m_path.exists():
        download(m_url, m_path)

    contracts, items = load_contracts(c_path)
    contracts["contract_id"] = pd.to_numeric(contracts["contract_id"], errors="coerce").astype("Int64")
    contracts["price"] = pd.to_numeric(contracts["price"], errors="coerce").fillna(0.0)
    contracts["start_location_id"] = pd.to_numeric(contracts["start_location_id"], errors="coerce").astype("Int64")
    c = contracts[(contracts["type"] == "item_exchange") & (contracts["price"] >= 0) & (contracts["price"] <= legacy.MAX_CONTRACT_PRICE) & contracts["start_location_id"].notna()].copy()
    if "date_expired" in c.columns:
        exp = pd.to_datetime(c["date_expired"], utc=True, errors="coerce")
        c = c[exp.isna() | (exp > pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=legacy.MIN_HOURS_TO_EXPIRE))].copy()
    valid = set(c["contract_id"].dropna().astype(int))
    ii = items[items["contract_id"].isin(valid)].copy()
    ii["contract_id"] = pd.to_numeric(ii["contract_id"], errors="coerce").astype("Int64")
    ii["_included"] = truthy_series(ii["is_included"])
    ii["_bpc"] = truthy_series(ii["is_blueprint_copy"])
    ii["quantity"] = pd.to_numeric(ii["quantity"], errors="coerce").fillna(0).astype(int)
    ii["type_id"] = pd.to_numeric(ii["type_id"], errors="coerce").fillna(0).astype(int)
    bpc_ids = set(ii.loc[ii["_bpc"], "contract_id"].dropna().astype(int))
    c = c[~c["contract_id"].isin(bpc_ids)].copy()
    inc = ii[ii["contract_id"].isin(c["contract_id"]) & ii["_included"] & (ii["quantity"] > 0) & (ii["type_id"] > 0)].copy()
    req = ii[ii["contract_id"].isin(c["contract_id"]) & ~ii["_included"] & (ii["quantity"] > 0) & (ii["type_id"] > 0)].copy()
    inc_groups = {int(cid): _aggregate(g) for cid, g in inc.groupby("contract_id", sort=False)}
    req_groups = {int(cid): _aggregate(g) for cid, g in req.groupby("contract_id", sort=False)}
    raw_inc = {int(cid): g.to_dict("records") for cid, g in inc.groupby("contract_id", sort=False)}
    raw_req = {int(cid): g.to_dict("records") for cid, g in req.groupby("contract_id", sort=False)}
    c = c[c["contract_id"].isin(inc_groups)].copy()
    if c.empty:
        pd.DataFrame().to_csv(RESULT, index=False)
        REPORT.write_text("# Opportunity Engine V3\n\nNo eligible contracts.\n", encoding="utf-8")
        return
    c_by_id = c.set_index("contract_id", drop=False)

    market = load_market_orders(m_path)
    snapshot_sells, snapshot_buys = prepare_jita_books(market)
    del market

    print(f"V3 contracts 2) diversified broad pass across {len(inc_groups):,} non-BPC contracts")
    broad = []
    for cid, itemq in inc_groups.items():
        if cid not in c_by_id.index:
            continue
        cm = c_by_id.loc[cid]
        if isinstance(cm, pd.DataFrame):
            cm = cm.iloc[0]
        price = safe_float(cm.get("price"), 0.0)
        requested = req_groups.get(cid, {})
        if not requested and price < legacy.MIN_CONTRACT_PRICE:
            continue
        floor = cash_floor_bundle(itemq, snapshot_buys, SALES_TAX_RATE)
        full = liquidate_bundle(itemq, snapshot_buys, SALES_TAX_RATE)
        procurement = procure_bundle(requested, snapshot_sells)
        req_cost = procurement["cost"] if procurement["complete"] else 0.0
        floor_profit = floor["net_after_tax"] - price - req_cost if (not requested or procurement["complete"]) else -1e30
        floor_base = price + req_cost
        floor_roi = floor_profit / floor_base if floor_base > 0 else (1.0 if floor_profit > 0 else 0.0)
        list_gross = _best_ask_gross(itemq, snapshot_sells) if not requested else 0.0
        broker, tax, relist = _fees(list_gross)
        list_profit = list_gross - broker - tax - relist - price
        list_roi = list_profit / (price + broker + relist) if price + broker + relist > 0 else 0.0
        snapshot_profit = max(floor_profit, list_profit)
        snapshot_roi = max(floor_roi, list_roi)
        broad.append({
            "contract_id": cid,
            "contract_price": price,
            "start_location_id": int(cm["start_location_id"]),
            "date_issued": cm.get("date_issued", ""),
            "date_expired": cm.get("date_expired", ""),
            "title": cm.get("title", ""),
            "included": itemq,
            "requested": requested,
            "snapshot_floor_complete": bool(full["complete"]),
            "snapshot_floor_coverage": floor["coverage"],
            "snapshot_profit": snapshot_profit,
            "snapshot_roi": snapshot_roi,
            "snapshot_list_profit": list_profit,
        })

    selected = select_candidate_union(broad, LIVE_LIMIT, PROFIT_QUOTA, ROI_QUOTA, RECENT_QUOTA)
    print(f"V3 contracts diversified live pool={len(selected)} (profit={PROFIT_QUOTA}, roi={ROI_QUOTA}, recent={RECENT_QUOTA})")
    if not selected:
        pd.DataFrame().to_csv(RESULT, index=False)
        return

    type_ids = {tid for p in selected for tid in set(p["included"]) | set(p["requested"])}
    types = fetch_many_ref("types", type_ids)
    gids = {type_group_id(v) for v in types.values()}
    gids.discard(None)
    groups = fetch_many_ref("groups", gids)
    locations, own_aid, own_name, own_ticker = _location_map(selected)

    prepared = []
    for p in selected:
        cid = int(p["contract_id"])
        loc = locations.get(int(p["start_location_id"]))
        if not loc or int(safe_float(loc.get("shortest_jumps_to_jita"), -1)) < 0:
            continue
        if bool(loc.get("is_player_structure")) and not bool(loc.get("friendly_sov")) and not bool(loc.get("friendly_region")):
            continue
        f_inc = analyze_contract_items(raw_inc.get(cid, []), types, groups)
        f_req = analyze_contract_items(raw_req.get(cid, []), types, groups) if p["requested"] else None
        if f_inc.has_highsec_restricted_ship or (f_req and f_req.has_highsec_restricted_ship):
            continue
        itemq = f_inc.adjusted_itemq
        if not itemq:
            continue
        snap_floor = cash_floor_bundle(itemq, snapshot_buys, SALES_TAX_RATE)
        skin_value = sum(float(r.get("gross", 0) or 0) for r in snap_floor["rows"] if legacy.is_skin_related(int(r["type_id"]), types, groups))
        skin_share = skin_value / snap_floor["gross"] if snap_floor["gross"] > 0 else 0.0
        if skin_share >= legacy.SKIN_MAJOR_SHARE:
            continue
        inc_m3 = sum(max(0.0, type_volume(types.get(tid))) * qty for tid, qty in itemq.items())
        req_m3 = sum(max(0.0, type_volume(types.get(tid))) * qty for tid, qty in p["requested"].items())
        inbound_haul = haul_reserve(inc_m3, loc)
        outbound_haul = haul_reserve(req_m3, loc) if p["requested"] else 0.0
        p = dict(p)
        p.update({"itemq": itemq, "feasibility": f_inc, "loc": loc, "skin_share": skin_share, "inc_m3": inc_m3, "req_m3": req_m3, "haul": inbound_haul + outbound_haul})
        prepared.append(p)

    buy_ids = {tid for p in prepared for tid in p["itemq"]}
    sell_ids = {tid for p in prepared for tid in set(p["requested"]) | set(p["itemq"])}
    live_buys, failed_buys, buy_at = fetch_live_jita_buy_books(buy_ids)
    live_sells, failed_sells, sell_at = fetch_live_jita_sell_books(sell_ids)
    sell_history_ids = {tid for p in prepared if not p["requested"] and p.get("snapshot_list_profit", 0) >= SELL_MIN_PROFIT * 0.25 for tid in p["itemq"]}
    price_history, failed_history = fetch_jita_price_history(sell_history_ids)

    rows = []
    for p in prepared:
        itemq = p["itemq"]
        requested = p["requested"]
        if set(itemq).intersection(failed_buys):
            buy_data_failed = True
        else:
            buy_data_failed = False
        full = liquidate_bundle(itemq, live_buys, SALES_TAX_RATE)
        floor = cash_floor_bundle(itemq, live_buys, SALES_TAX_RATE)
        immediate_profit = full["net_after_tax"] - p["contract_price"] - p["haul"] if full["complete"] else -1e30
        immediate_roi = immediate_profit / (p["contract_price"] + p["haul"]) if p["contract_price"] + p["haul"] > 0 else 0.0

        if not requested and not full["complete"] and not buy_data_failed and floor["has_executable_value"]:
            profit = floor["net_after_tax"] - p["contract_price"] - p["haul"]
            invested = p["contract_price"] + p["haul"]
            roi = profit / invested if invested > 0 else 0.0
            stress_profit = floor["stress_net_after_tax"] - p["contract_price"] - p["haul"]
            status = classify_execution_status(True, profit, roi, stress_profit, 0.0, [])
            if profit >= legacy.MIN_NET_PROFIT and roi >= legacy.MIN_NET_ROI and status != "DANGER":
                rows.append(_row(p, types, "CASH_FLOOR", status, profit, roi, stress_profit, floor["gross"], floor["coverage"], 0.0, 0.0, 0.0, buy_at, own_aid, own_name, own_ticker, "Unsold remainder valued at 0 ISK"))

        if requested:
            data_failed = bool(set(requested).intersection(failed_sells)) or buy_data_failed
            procurement = procure_bundle(requested, live_sells)
            if not data_failed and procurement["complete"]:
                base_cost = p["contract_price"] + procurement["cost"] + p["haul"]
                full_profit = full["net_after_tax"] - base_cost if full["complete"] else -1e30
                floor_profit = floor["net_after_tax"] - base_cost
                use_full = full["complete"] and full_profit >= floor_profit
                proceeds = full["net_after_tax"] if use_full else floor["net_after_tax"]
                gross = full["gross"] if use_full else floor["gross"]
                coverage = 1.0 if use_full else floor["coverage"]
                profit = proceeds - base_cost
                roi = profit / base_cost if base_cost > 0 else 0.0
                if procurement["stress_complete"]:
                    stress_proceeds = full["stress_net_after_tax"] if use_full else floor["stress_net_after_tax"]
                    stress_profit = stress_proceeds - p["contract_price"] - procurement["stress_cost"] - p["haul"]
                else:
                    stress_profit = -base_cost
                status = classify_execution_status(True, profit, roi, stress_profit, 0.0, [])
                if profit >= legacy.MIN_NET_PROFIT and roi >= legacy.MIN_NET_ROI and status != "DANGER":
                    cls = "EXCHANGE_FULL" if use_full else "EXCHANGE_CASH_FLOOR"
                    note = "Requested goods priced from live Jita sells; leftover received goods are 0 ISK" if not use_full else "Requested goods priced from live Jita sells"
                    rows.append(_row(p, types, cls, status, profit, roi, stress_profit, gross, coverage, procurement["cost"], procurement["stress_cost"], procurement["max_slippage_pct"], max(buy_at, sell_at), own_aid, own_name, own_ticker, note))

        if not requested and not set(itemq).intersection(failed_sells | failed_history):
            sell_quote = conservative_sell_bundle(itemq, live_sells, price_history)
            if sell_quote["complete"] and sell_quote["fill_days"] <= SELL_MAX_FILL_DAYS:
                broker, tax, relist = _fees(sell_quote["gross"])
                profit = sell_quote["gross"] - broker - tax - relist - p["contract_price"] - p["haul"]
                invested = p["contract_price"] + p["haul"] + broker + relist
                roi = profit / invested if invested > 0 else 0.0
                sb, st, sr = _fees(sell_quote["stress_gross"])
                stress_profit = sell_quote["stress_gross"] - sb - st - sr - p["contract_price"] - p["haul"]
                incremental = profit - max(0.0, immediate_profit)
                status = "SAFE" if stress_profit > 0 else "CHANGED"
                if profit >= SELL_MIN_PROFIT and roi >= SELL_MIN_ROI and incremental >= SELL_MIN_INCREMENT and status == "SAFE":
                    rows.append(_row(p, types, "LIQUIDITY_SELL", status, profit, roi, stress_profit, sell_quote["gross"], 1.0, 0.0, 0.0, sell_quote["fill_days"], sell_at, own_aid, own_name, own_ticker, "Conservative exit=min(live ask,7d VWAP,30d VWAP) with haircut; includes broker/tax/relist"))

    priority = {"CASH_FLOOR": 0, "EXCHANGE_FULL": 1, "EXCHANGE_CASH_FLOOR": 2, "LIQUIDITY_SELL": 3}
    rows.sort(key=lambda r: (r["execution_status"] != "SAFE", priority.get(r["opportunity_class"], 9), -r["net_profit"], -r["net_roi"]))
    pd.DataFrame(rows).to_csv(RESULT, index=False)
    _write_report(rows, c_modified, m_modified)
    counts = pd.Series([r["opportunity_class"] for r in rows]).value_counts().to_dict() if rows else {}
    print(f"V3 contracts done: {len(rows)} opportunities {counts}")


def _row(p, types, cls, status, profit, roi, stress_profit, gross, coverage, requested_cost, requested_stress_cost, extra_metric, verified_at, own_aid, own_name, own_ticker, note):
    loc = p["loc"]
    return {
        "engine_version": ENGINE,
        "opportunity_class": cls,
        "execution_status": status,
        "contract_id": int(p["contract_id"]),
        "contract_price": p["contract_price"],
        "net_profit": profit,
        "net_roi": roi,
        "stress_net_profit": stress_profit,
        "executable_or_exit_gross": gross,
        "cash_floor_coverage": coverage,
        "requested_goods_cost": requested_cost,
        "requested_goods_stress_cost": requested_stress_cost,
        "extra_metric": extra_metric,
        "haul_reserve": p["haul"],
        "included_volume_m3": p["inc_m3"],
        "requested_volume_m3": p["req_m3"],
        "included_items": _item_text(p["itemq"], types),
        "requested_items": _item_text(p["requested"], types),
        "skin_value_share": p["skin_share"],
        "verified_at": verified_at,
        "note": note,
        "title": p.get("title", ""),
        "date_issued": p.get("date_issued", ""),
        "date_expired": p.get("date_expired", ""),
        "start_location_id": p["start_location_id"],
        "station_name": loc.get("station_name", ""),
        "system_id": loc.get("system_id", 0),
        "system_name": loc.get("system_name", ""),
        "region_id": loc.get("region_id", 0),
        "security": loc.get("security", 0),
        "shortest_jumps_to_jita": loc.get("shortest_jumps_to_jita", -1),
        "risk_tier": loc.get("risk_tier", ""),
        "risk_rank": loc.get("risk_rank", 5),
        "friendly_alliance_id": own_aid,
        "friendly_alliance_name": own_name,
        "friendly_alliance_ticker": own_ticker,
        "type_quantities_json": json.dumps(p["itemq"], sort_keys=True, separators=(",", ":")),
        "requested_quantities_json": json.dumps(p["requested"], sort_keys=True, separators=(",", ":")),
    }


def _write_report(rows, c_modified, m_modified):
    lines = ["# Opportunity Engine V3 — supplemental contract opportunities", "", f"- Contract snapshot: `{c_modified}`", f"- Market snapshot: `{m_modified}`", "- V2 immediate-buy SAFE logic remains unchanged; V3 is additive and only covers opportunities V2 tends to miss.", "- CASH_FLOOR values unsold remainder at zero; EXCHANGE requires requested goods to be fully purchasable; LIQUIDITY_SELL uses live asks plus 7d/30d history and a price haircut.", ""]
    if rows:
        lines += ["| # | Class | Status | Contract | Net | ROI | Stress | Coverage | System |", "|---:|---|---|---:|---:|---:|---:|---:|---|"]
        for i, r in enumerate(rows[:100], 1):
            lines.append(f"| {i} | {r['opportunity_class']} | {r['execution_status']} | {r['contract_id']} | {r['net_profit']/1e6:.1f}M | {r['net_roi']:.1%} | {r['stress_net_profit']/1e6:.1f}M | {r['cash_floor_coverage']:.0%} | {str(r['system_name']).replace('|','/')} |")
    else:
        lines.append("No V3 supplemental opportunity passed live checks.")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
