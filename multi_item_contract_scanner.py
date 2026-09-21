from __future__ import annotations

import json
import math
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
    classify_execution_status,
    drop_best_price_level,
    estimate_transport,
    fetch_live_jita_buy_books,
    liquidate_bundle,
    opportunity_score,
    score_grade,
    snapshot_change_pct,
)
from opportunity_engine_v3 import partial_liquidation
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

MIN_TYPES = int(os.getenv("MULTI_MIN_TYPES", "2"))
MIN_CONTRACT_PRICE = float(os.getenv("MULTI_MIN_CONTRACT_PRICE", "1000000"))
MAX_CONTRACT_PRICE = float(os.getenv("MULTI_MAX_CONTRACT_PRICE", "5000000000"))
MIN_HOURS_TO_EXPIRE = float(os.getenv("MULTI_MIN_HOURS_TO_EXPIRE", "0.5"))
LIVE_LIMIT = int(os.getenv("MULTI_LIVE_LIMIT", "300"))
PER_METRIC = int(os.getenv("MULTI_PER_METRIC", "120"))
NEWEST_COUNT = int(os.getenv("MULTI_NEWEST_COUNT", "60"))
TOP_OUTPUT = int(os.getenv("MULTI_TOP", "250"))
SKIN_MAJOR_SHARE = float(os.getenv("DEAL_SKIN_MAJOR_SHARE", "0.50"))

INSTANT_MIN_PROFIT = float(os.getenv("MULTI_INSTANT_MIN_PROFIT", "30000000"))
INSTANT_MIN_ROI = float(os.getenv("MULTI_INSTANT_MIN_ROI", "0.10"))
CASH_MIN_PROFIT = float(os.getenv("MULTI_CASH_FLOOR_MIN_PROFIT", "30000000"))
CASH_MIN_ROI = float(os.getenv("MULTI_CASH_FLOOR_MIN_ROI", "0.10"))
SAFE_PRICE_CHANGE_PCT = float(os.getenv("MULTI_SAFE_PRICE_CHANGE_PCT", "0.15"))

RESULT = LATEST / "multi_item_contract_deals.csv"
ALL_RESULT = LATEST / "multi_item_contract_all.csv"
REPORT = LATEST / "multi_item_value_report.md"


def _aggregate(df: pd.DataFrame) -> dict[int, int]:
    return legacy.aggregate_items(df)


def _metadata(type_ids):
    types = fetch_many_ref("types", type_ids)
    gids = {type_group_id(v) for v in types.values()}
    gids.discard(None)
    groups = fetch_many_ref("groups", gids)
    return types, groups


def _prefilter_market_executable_groups(df):
    if df.empty:
        return {}, {}
    singleton_tids = set()
    records = df.to_dict("records")
    for row in records:
        raw = row.get("is_singleton", row.get("singleton", False))
        if str(raw or "").strip().lower() in {"1", "true", "t", "yes", "y"}:
            tid = int(row.get("type_id") or 0)
            if tid > 0:
                singleton_tids.add(tid)
    singleton_types, singleton_groups = _metadata(singleton_tids) if singleton_tids else ({}, {})
    grouped = {}
    excluded = {}
    for cid, g in df.groupby("contract_id", sort=False):
        q, ex = aggregate_market_executable_items(g.to_dict("records"), singleton_types, singleton_groups)
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


def _safe_location(loc):
    if not loc:
        return False
    if int(legacy.safe_num(loc.get("system_id"), 0)) <= 0:
        return False
    if int(legacy.safe_num(loc.get("shortest_jumps_to_jita"), -1)) < 0:
        return False
    if bool(loc.get("is_player_structure")) and not bool(loc.get("friendly_sov")) and not bool(loc.get("friendly_region")):
        return False
    return True


def _partial_stress(itemq, books):
    stressed = {int(tid): drop_best_price_level(books.get(int(tid), [])) for tid in itemq}
    return partial_liquidation(itemq, stressed, SALES_TAX_RATE)


def _volume(itemq, types):
    return sum(max(0.0, type_volume(types.get(int(tid)))) * int(qty) for tid, qty in itemq.items())


def _top_value_lines(quote, types, limit=12):
    rows = sorted(quote.get("rows", []), key=lambda r: float(r.get("gross", 0) or 0), reverse=True)
    out = []
    for r in rows[:limit]:
        gross = float(r.get("gross", 0) or 0)
        if gross <= 0:
            continue
        tid = int(r["type_id"])
        filled = int(r.get("filled", r.get("quantity", 0)) or 0)
        requested = int(r.get("quantity", 0) or 0)
        out.append(f"{name_en(types.get(tid), str(tid))} {filled}/{requested}≈{gross/1e6:.1f}M")
    return " | ".join(out)


def _diverse_candidates(rows):
    selected = {}
    metrics = ("snapshot_profit", "snapshot_roi", "snapshot_value_ratio")
    for metric in metrics:
        ranked = sorted(rows, key=lambda r: float(r.get(metric, -math.inf)), reverse=True)
        for row in ranked[:PER_METRIC]:
            selected[int(row["contract_id"])] = row
    newest = sorted(rows, key=lambda r: str(r.get("date_issued", "")), reverse=True)
    for row in newest[:NEWEST_COUNT]:
        selected[int(row["contract_id"])] = row
    ranked_all = sorted(rows, key=lambda r: (r["snapshot_profit"], r["snapshot_roi"]), reverse=True)
    for row in ranked_all:
        if len(selected) >= LIVE_LIMIT:
            break
        selected.setdefault(int(row["contract_id"]), row)
    out = list(selected.values())
    out.sort(key=lambda r: (r["snapshot_profit"], r["snapshot_roi"]), reverse=True)
    return out[:LIVE_LIMIT]


def _cash_status(profit, roi, stress_profit, change_pct, fatal=False):
    if fatal or profit < CASH_MIN_PROFIT or roi < CASH_MIN_ROI:
        return "DANGER"
    if stress_profit <= 0 or abs(change_pct) > SAFE_PRICE_CHANGE_PCT:
        return "CHANGED"
    return "SAFE"


def _write_empty(message: str):
    LATEST.mkdir(parents=True, exist_ok=True)
    pd.DataFrame().to_csv(ALL_RESULT, index=False)
    pd.DataFrame().to_csv(RESULT, index=False)
    REPORT.write_text(f"# Independent multi-item value engine\n\n{message}\n", encoding="utf-8")


def main():
    LATEST.mkdir(parents=True, exist_ok=True)
    print("Independent multi-item value engine: INSTANT + CASH_FLOOR")

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
    c = contracts[
        (contracts["type"] == "item_exchange")
        & (contracts["price"] >= MIN_CONTRACT_PRICE)
        & (contracts["price"] <= MAX_CONTRACT_PRICE)
        & contracts["start_location_id"].notna()
    ].copy()
    if "date_expired" in c.columns:
        exp = pd.to_datetime(c["date_expired"], utc=True, errors="coerce")
        c = c[exp.isna() | (exp > pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=MIN_HOURS_TO_EXPIRE))].copy()

    valid = set(c["contract_id"].dropna().astype(int))
    ii = items[items["contract_id"].isin(valid)].copy()
    ii["contract_id"] = pd.to_numeric(ii["contract_id"], errors="coerce").astype("Int64")
    ii["_included"] = truthy_series(ii["is_included"])
    ii["_bpc"] = truthy_series(ii["is_blueprint_copy"])
    ii["quantity"] = pd.to_numeric(ii["quantity"], errors="coerce").fillna(0).astype(int)
    ii["type_id"] = pd.to_numeric(ii["type_id"], errors="coerce").fillna(0).astype(int)

    requested_ids = set(ii.loc[~ii["_included"], "contract_id"].dropna().astype(int))
    bpc_ids = set(ii.loc[ii["_bpc"], "contract_id"].dropna().astype(int))
    usable = valid - requested_ids - bpc_ids
    inc = ii[ii["contract_id"].isin(usable) & ii["_included"] & (ii["quantity"] > 0) & (ii["type_id"] > 0)].copy()
    raw_groups_all = {int(cid): g.to_dict("records") for cid, g in inc.groupby("contract_id", sort=False)}
    grouped_all, early_singletons = _prefilter_market_executable_groups(inc)
    grouped = {cid: q for cid, q in grouped_all.items() if len(q) >= MIN_TYPES}
    raw_groups = {cid: raw_groups_all[cid] for cid in grouped if cid in raw_groups_all}
    early_singleton_qty = sum(sum(x.values()) for x in early_singletons.values())
    print(
        f"multi market-ineligible singleton prefilter: contracts={len(early_singletons):,} "
        f"qty={early_singleton_qty:,}"
    )
    c = c[c["contract_id"].isin(grouped)].copy()
    print(f"multi universe={len(grouped):,} contracts with >= {MIN_TYPES} item types")
    if c.empty:
        _write_empty("No eligible multi-item contracts.")
        return

    c_by_id = c.set_index("contract_id", drop=False)
    market = load_market_orders(m_path)
    _, snapshot_buys = prepare_jita_books(market)
    del market

    broad_rows = []
    for cid, itemq in grouped.items():
        cm = c_by_id.loc[cid]
        if isinstance(cm, pd.DataFrame):
            cm = cm.iloc[0]
        price = legacy.safe_num(cm.get("price"))
        cash = partial_liquidation(itemq, snapshot_buys, SALES_TAX_RATE)
        profit = float(cash["net_after_tax"] or 0) - price
        roi = profit / price if price > 0 else -math.inf
        ratio = float(cash["net_after_tax"] or 0) / price if price > 0 else 0.0
        broad_rows.append({
            "contract_id": cid,
            "contract_price": price,
            "start_location_id": int(cm["start_location_id"]),
            "date_issued": cm.get("date_issued", ""),
            "date_expired": cm.get("date_expired", ""),
            "title": cm.get("title", ""),
            "itemq_raw": itemq,
            "snapshot_cash": cash,
            "snapshot_profit": profit,
            "snapshot_roi": roi,
            "snapshot_value_ratio": ratio,
        })

    selected = _diverse_candidates(broad_rows)
    print(f"multi live candidate pool={len(selected):,} from universe={len(broad_rows):,}")
    if not selected:
        _write_empty("No live candidates selected.")
        return

    locations, own_aid, own_name, own_ticker = _resolve_locations(selected)
    location_removed = 0
    selected2 = []
    for p in selected:
        loc = locations.get(int(p["start_location_id"]))
        if not _safe_location(loc):
            location_removed += 1
            continue
        q = dict(p)
        q["loc"] = loc
        selected2.append(q)
    selected = selected2
    print(f"multi reachable/fail-closed candidates={len(selected):,}; location_removed={location_removed}")
    if not selected:
        _write_empty("All selected candidates failed location/access checks.")
        return

    all_tids = set()
    for p in selected:
        cid = int(p["contract_id"])
        for raw in raw_groups.get(cid, []):
            try:
                tid = int(raw.get("type_id") or 0)
            except Exception:
                tid = 0
            if tid > 0:
                all_tids.add(tid)
    types, groups = _metadata(all_tids)

    feasible = []
    capital_removed = skin_removed = rig_adjusted = singleton_adjusted = 0
    for p in selected:
        f = analyze_contract_items(raw_groups.get(int(p["contract_id"]), []), types, groups)
        if f.has_highsec_restricted_ship:
            capital_removed += 1
            continue
        if not f.adjusted_itemq or len(f.adjusted_itemq) < MIN_TYPES:
            continue
        if f.excluded_rigs:
            rig_adjusted += 1
        if f.excluded_market_singletons:
            singleton_adjusted += 1
        snap = partial_liquidation(f.adjusted_itemq, snapshot_buys, SALES_TAX_RATE)
        gross = float(snap["gross"] or 0)
        skin_value = sum(
            float(r.get("gross", 0) or 0)
            for r in snap["rows"]
            if legacy.is_skin_related(int(r["type_id"]), types, groups)
        )
        skin_share = skin_value / gross if gross > 0 else 0.0
        if gross > 0 and skin_share >= SKIN_MAJOR_SHARE:
            skin_removed += 1
            continue
        q = dict(p)
        q["itemq"] = f.adjusted_itemq
        q["feasibility"] = f
        q["skin_value_share"] = skin_share
        q["excluded_market_singleton_types"] = len(f.excluded_market_singletons)
        q["excluded_market_singleton_qty"] = sum(f.excluded_market_singletons.values())
        q["snapshot_cash_adjusted"] = snap
        feasible.append(q)

    print(
        f"multi feasible={len(feasible):,}; capital_removed={capital_removed} "
        f"skin_removed={skin_removed} rig_adjusted={rig_adjusted} singleton_adjusted={singleton_adjusted}"
    )
    if not feasible:
        _write_empty("No feasible candidates after item checks.")
        return

    live_type_ids = {int(tid) for p in feasible for tid in p["itemq"]}
    print(f"multi live Jita buy books: contracts={len(feasible):,} unique_types={len(live_type_ids):,}")
    live_books, failed_types, live_at = fetch_live_jita_buy_books(live_type_ids)

    rows = []
    diagnostics = []
    a_count = b_count = safe_count = changed_count = 0
    for p in feasible:
        itemq = p["itemq"]
        loc = p["loc"]
        price = float(p["contract_price"])
        total_m3 = _volume(itemq, types)
        full_haul = haul_reserve(total_m3, loc)

        full = liquidate_bundle(itemq, live_books, SALES_TAX_RATE)
        full_profit = float(full["net_after_tax"] or 0) - full_haul - price
        full_base = price + full_haul
        full_roi = full_profit / full_base if full_base > 0 else 0.0
        full_stress_profit = float(full["stress_net_after_tax"] or 0) - full_haul - price
        full_change = snapshot_change_pct(p["snapshot_cash_adjusted"]["gross"], full["gross"])
        full_failed = bool(set(itemq).intersection(failed_types))
        full_status = classify_execution_status(
            bool(full["complete"]), full_profit, full_roi, full_stress_profit, full_change,
            ["live_jita_fetch_failed"] if full_failed else [],
        )
        a_ok = bool(full["complete"]) and full_profit >= INSTANT_MIN_PROFIT and full_roi >= INSTANT_MIN_ROI and full_status != "DANGER"

        cash = partial_liquidation(itemq, live_books, SALES_TAX_RATE)
        matched_q = {int(tid): int(qty) for tid, qty in cash.get("matched_itemq", {}).items() if int(qty) > 0}
        matched_m3 = _volume(matched_q, types)
        cash_haul = haul_reserve(matched_m3, loc)
        cash_profit = float(cash["net_after_tax"] or 0) - cash_haul - price
        cash_base = price + cash_haul
        cash_roi = cash_profit / cash_base if cash_base > 0 else 0.0
        stress_cash = _partial_stress(itemq, live_books)
        stress_cash_profit = float(stress_cash["net_after_tax"] or 0) - cash_haul - price
        cash_change = snapshot_change_pct(p["snapshot_cash_adjusted"]["gross"], cash["gross"])
        cash_status = _cash_status(
            cash_profit, cash_roi, stress_cash_profit, cash_change,
            fatal=(cash.get("filled_units", 0) <= 0),
        )
        b_ok = cash_profit >= CASH_MIN_PROFIT and cash_roi >= CASH_MIN_ROI and cash_status != "DANGER"

        diagnostics.append({
            "contract_id": int(p["contract_id"]),
            "contract_price": price,
            "item_type_count": len(itemq),
            "full_complete": bool(full["complete"]),
            "full_profit": full_profit,
            "full_roi": full_roi,
            "full_status": full_status,
            "cash_profit": cash_profit,
            "cash_roi": cash_roi,
            "cash_status": cash_status,
            "cash_coverage": float(cash.get("coverage", 0) or 0),
            "cash_unvalued_units": max(0, int(cash.get("requested_units", 0) or 0) - int(cash.get("filled_units", 0) or 0)),
            "risk_tier": loc.get("risk_tier", ""),
            "system_name": loc.get("system_name", ""),
        })

        if not (a_ok or b_ok):
            continue

        if a_ok:
            deal_class = "A 多件即时兑现"
            status = full_status
            chosen = full
            chosen_profit = full_profit
            chosen_roi = full_roi
            chosen_stress = full_stress_profit
            chosen_change = full_change
            chosen_haul = full_haul
            chosen_m3 = total_m3
            matched_for_display = {int(tid): int(qty) for tid, qty in itemq.items()}
            a_count += 1
        else:
            deal_class = "B 多件现金底价"
            status = cash_status
            chosen = cash
            chosen_profit = cash_profit
            chosen_roi = cash_roi
            chosen_stress = stress_cash_profit
            chosen_change = cash_change
            chosen_haul = cash_haul
            chosen_m3 = matched_m3
            matched_for_display = matched_q
            b_count += 1

        if status == "SAFE":
            safe_count += 1
        elif status == "CHANGED":
            changed_count += 1

        transport = estimate_transport(chosen_m3, int(legacy.safe_num(loc.get("shortest_jumps_to_jita"), 0)), chosen_profit)
        density = chosen_profit / chosen_m3 if chosen_m3 > 0 else chosen_profit
        score = opportunity_score(
            chosen_profit,
            chosen_roi,
            density,
            80.0 if deal_class.startswith("A") else 70.0,
            chosen_stress,
            loc.get("risk_rank", 5),
            transport.hours,
            chosen_change,
            status,
        )
        rows.append({
            "engine_version": "Independent Multi Value V1",
            "deal_class": deal_class,
            "valuation_basis": "LIVE_JITA_FULL_LIQUIDATION" if deal_class.startswith("A") else "LIVE_JITA_PARTIAL_CASH_FLOOR_LEFTOVERS_ZERO",
            "execution_status": status,
            "score_grade": score_grade(score),
            "opportunity_score": score,
            "contract_id": int(p["contract_id"]),
            "contract_price": price,
            "item_type_count": len(itemq),
            "item_total_units": sum(itemq.values()),
            "type_quantities_json": json.dumps(itemq, sort_keys=True, separators=(",", ":")),
            "matched_type_quantities_json": json.dumps(matched_for_display, sort_keys=True, separators=(",", ":")),
            "top_value_items": _top_value_lines(chosen, types),
            "jita_buy_gross": float(chosen.get("gross", 0) or 0),
            "sales_tax_if_instant": float(chosen.get("sales_tax", 0) or 0),
            "instant_liquidation_net_value": float(chosen.get("net_after_tax", 0) or 0) - chosen_haul,
            "instant_net_profit": chosen_profit,
            "instant_net_roi": chosen_roi,
            "chosen_estimated_value": float(chosen.get("net_after_tax", 0) or 0) - chosen_haul,
            "chosen_value_gap": chosen_profit,
            "chosen_discount": chosen_profit / max(1.0, float(chosen.get("net_after_tax", 0) or 0) - chosen_haul),
            "chosen_roi": chosen_roi,
            "stress_net_profit": chosen_stress,
            "snapshot_jita_buy_gross": float(p["snapshot_cash_adjusted"]["gross"] or 0),
            "snapshot_change_pct": chosen_change,
            "live_revalidated_at": live_at,
            "buy_unit_coverage": float(chosen.get("coverage", 0) or 0),
            "buy_filled_units": int(chosen.get("filled_units", 0) or 0),
            "total_units": int(chosen.get("requested_units", 0) or 0),
            "unvalued_units_zero": max(0, int(chosen.get("requested_units", 0) or 0) - int(chosen.get("filled_units", 0) or 0)),
            "matched_volume_m3": chosen_m3,
            "total_m3": total_m3,
            "haul_reserve": chosen_haul,
            "profit_per_m3": density,
            "skin_value_share": p["skin_value_share"],
            "excluded_rig_types": len(p["feasibility"].excluded_rigs),
            "excluded_rig_qty": sum(p["feasibility"].excluded_rigs.values()),
            "excluded_market_singleton_types": p["excluded_market_singleton_types"],
            "excluded_market_singleton_qty": p["excluded_market_singleton_qty"],
            "has_assembled_ship": p["feasibility"].has_ship,
            "highsec_restricted_ship": p["feasibility"].has_highsec_restricted_ship,
            "transport_trips": transport.trips,
            "estimated_execution_hours": transport.hours,
            "estimated_isk_per_hour": transport.isk_per_hour,
            "contract_title": p.get("title", ""),
            "date_expired": p.get("date_expired", ""),
            "contracts_snapshot_modified": c_modified,
            "market_snapshot_modified": m_modified,
            "friendly_alliance_id": own_aid,
            "friendly_alliance_name": own_name,
            "friendly_alliance_ticker": own_ticker,
            "eve_contract_url": f"https://eve-contract-opener.99617224.workers.dev/c/{p['contract_id']}",
            **loc,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        status_rank = {"SAFE": 0, "CHANGED": 1}
        class_rank = {"A 多件即时兑现": 0, "B 多件现金底价": 1}
        df["_sr"] = df["execution_status"].map(status_rank).fillna(9)
        df["_cr"] = df["deal_class"].map(class_rank).fillna(9)
        df.sort_values(["_sr", "_cr", "opportunity_score", "chosen_value_gap"], ascending=[True, True, False, False], inplace=True)
        df.drop(columns=["_sr", "_cr"], inplace=True)
    df.to_csv(ALL_RESULT, index=False)
    df.head(TOP_OUTPUT).to_csv(RESULT, index=False)

    lines = [
        "# Independent multi-item value engine",
        "",
        f"- Multi-item universe: `{len(grouped):,}`",
        f"- Live candidate pool: `{len(selected):,}`",
        f"- Feasible after location/item checks: `{len(feasible):,}`",
        f"- Live Jita type books: `{len(live_type_ids):,}`",
        f"- Final A instant: `{a_count}`",
        f"- Final B cash-floor: `{b_count}`",
        f"- SAFE: `{safe_count}`; CHANGED: `{changed_count}`",
        f"- Instant threshold: profit >= `{INSTANT_MIN_PROFIT:,.0f}` ISK, ROI >= `{INSTANT_MIN_ROI:.1%}`",
        f"- Cash-floor threshold: profit >= `{CASH_MIN_PROFIT:,.0f}` ISK, ROI >= `{CASH_MIN_ROI:.1%}`",
        "- Cash-floor values unmatched leftovers at zero and only reserves hauling for the matched cash-producing subset.",
        "",
    ]
    if not df.empty:
        lines += [
            "| # | Class | Status | Grade | Contract | Price | Net | ROI | Coverage | Types | Risk |",
            "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
        for i, r in enumerate(df.head(30).to_dict("records"), 1):
            lines.append(
                f"| {i} | {r['deal_class']} | {r['execution_status']} | {r['score_grade']} | {int(r['contract_id'])} | "
                f"{r['contract_price']/1e6:.1f}M | {r['chosen_value_gap']/1e6:.1f}M | {r['chosen_roi']:.1%} | "
                f"{r['buy_unit_coverage']:.1%} | {int(r['item_type_count'])} | {r.get('risk_tier','')} |"
            )
    else:
        lines.append("No opportunity passed the live thresholds.")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        f"multi independent done: rows={len(df)} A={a_count} B={b_count} "
        f"SAFE={safe_count} CHANGED={changed_count} -> {RESULT}"
    )
    if diagnostics:
        diag = pd.DataFrame(diagnostics)
        diag.sort_values(["cash_profit", "cash_roi"], ascending=[False, False], inplace=True)
        print("multi near-miss cash-floor TOP20:")
        print(diag.head(20).to_string(index=False))
        diag_roi = diag.sort_values(["cash_roi", "cash_profit"], ascending=[False, False])
        print("multi near-miss cash-floor ROI TOP20:")
        print(diag_roi.head(20).to_string(index=False))
    if not df.empty:
        cols = ["contract_id", "deal_class", "execution_status", "contract_price", "chosen_value_gap", "chosen_roi", "buy_unit_coverage", "item_type_count", "risk_tier"]
        print(df[cols].head(20).to_string(index=False))


if __name__ == "__main__":
    main()
