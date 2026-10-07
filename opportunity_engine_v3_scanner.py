from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

import buy_only_contract_scanner as legacy
from candidate_pool import record_candidate_pool, select_candidate_pool
from contract_deal_scanner import (
    BROKER_FEE_RATE,
    RELIST_RESERVE_RATE,
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
    drop_best_price_level,
    opportunity_score,
    profit_density,
    score_grade,
)
from opportunity_engine_v3 import (
    LIST_MAX_FILL_DAYS,
    conservative_listing_bundle,
    fetch_live_jita_books,
    fetch_market_history,
    material_change,
    partial_liquidation,
    procurement_cost,
)
from scanner_source import (
    DATA,
    LATEST,
    STATE,
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
from v3_engine import (
    ExecutionProof,
    MarketSnapshot,
    PolicyConfig,
    RejectionFunnel,
    contract_fingerprint,
    evaluate_execution,
    evaluate_listing,
    is_full_cash_exit,
    load_fingerprints,
    save_fingerprints,
)

ENGINE_VERSION = "Opportunity Engine V3 Redesign 2026-10-07"

LIVE_LIMIT = int(os.getenv("V3_PUBLIC_LIVE_LIMIT", "600"))
V3_PROFIT_SHARE = float(os.getenv("V3_PUBLIC_PROFIT_SHARE", "0.25"))
V3_ROI_SHARE = float(os.getenv("V3_PUBLIC_ROI_SHARE", "0.15"))
V3_LIST_PROFIT_SHARE = float(os.getenv("V3_PUBLIC_LIST_PROFIT_SHARE", "0.10"))
V3_LIST_ROI_SHARE = float(os.getenv("V3_PUBLIC_LIST_ROI_SHARE", "0.05"))
V3_CHANGE_SHARE = float(os.getenv("V3_PUBLIC_CHANGE_SHARE", "0.15"))
V3_NEWEST_SHARE = float(os.getenv("V3_PUBLIC_NEWEST_SHARE", "0.13"))
V3_EXPLORATION_SHARE = float(os.getenv("V3_PUBLIC_EXPLORATION_SHARE", "0.12"))
V3_DIVERSITY_SHARE = float(os.getenv("V3_PUBLIC_DIVERSITY_SHARE", "0.05"))
LIST_HISTORY_LIMIT = int(os.getenv("V3_LIST_HISTORY_LIMIT", "160"))

FULL_CASH_RESULT = LATEST / "v3_full_cash.csv"
CASH_RESULT = LATEST / "v3_cash_floor.csv"
BARTER_RESULT = LATEST / "v3_barter.csv"
LIST_RESULT = LATEST / "v3_conservative_listing.csv"
RESEARCH_RESULT = LATEST / "v3_research.csv"
ALL_RESULT = LATEST / "v3_opportunities.csv"
FUNNEL_JSON = LATEST / "v3_rejection_funnel.json"
REPORT = LATEST / "v3_public_opportunities.md"
FINGERPRINT_STATE = STATE / "v3_contract_fingerprints.json"
POOL_STATE = STATE / "candidate_pool_state.json"


def _aggregate(df: pd.DataFrame) -> dict[int, int]:
    return legacy.aggregate_items(df)


def _metadata(type_ids):
    types = fetch_many_ref("types", type_ids)
    gids = {type_group_id(v) for v in types.values()}
    gids.discard(None)
    return types, fetch_many_ref("groups", gids)


def _prefilter_market_executable_groups(df):
    """Conservatively remove instance-like rows before candidate ranking."""
    if df.empty:
        return {}, {}

    candidate_meta_tids = set()
    for _, g in df.groupby("contract_id", sort=False):
        records = g.to_dict("records")
        unit_counts = {}
        for row in records:
            try:
                tid = int(row.get("type_id") or 0)
                qty = int(row.get("quantity") or 0)
            except Exception:
                continue
            if tid <= 0 or qty <= 0:
                continue
            if qty == 1:
                unit_counts[tid] = unit_counts.get(tid, 0) + 1
            raw = row.get("is_singleton", row.get("singleton", False))
            if str(raw or "").strip().lower() in {"1", "true", "t", "yes", "y"}:
                candidate_meta_tids.add(tid)
        for tid, count in unit_counts.items():
            if count >= 2:
                candidate_meta_tids.add(tid)

    meta_types, meta_groups = _metadata(candidate_meta_tids) if candidate_meta_tids else ({}, {})
    grouped, excluded = {}, {}
    for cid, g in df.groupby("contract_id", sort=False):
        q, ex = aggregate_market_executable_items(g.to_dict("records"), meta_types, meta_groups)
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
    if int(float(loc.get("system_id", 0) or 0)) <= 0:
        return False
    if int(float(loc.get("shortest_jumps_to_jita", -1) or -1)) < 0:
        return False
    if bool(loc.get("is_player_structure")) and not bool(loc.get("friendly_sov")) and not bool(loc.get("friendly_region")):
        return False
    return True


def _snapshot_partial(itemq, buy_books):
    return partial_liquidation(itemq, buy_books, SALES_TAX_RATE)


def _snapshot_procure(itemq, sell_books):
    return procurement_cost(itemq, sell_books)


def _volume(itemq, types):
    return sum(max(0.0, type_volume(types.get(int(tid)))) * int(qty) for tid, qty in itemq.items())


def _matched_volume(quote, types):
    return _volume(quote.get("matched_itemq", {}), types)


def _stress_partial(itemq, books):
    stressed = {int(tid): drop_best_price_level(books.get(int(tid), [])) for tid in itemq}
    return partial_liquidation(itemq, stressed, SALES_TAX_RATE)


def _row_items(itemq, types, limit=14):
    return " | ".join(
        f"{name_en(types.get(int(tid)), str(tid))} x{int(qty)}"
        for tid, qty in list(itemq.items())[:limit]
    )


def _top_value_lines(quote, types, limit=8):
    rows = sorted(quote.get("rows", []), key=lambda r: float(r.get("gross", 0) or 0), reverse=True)
    return " | ".join(
        f"{name_en(types.get(int(r['type_id'])), str(r['type_id']))} "
        f"{int(r.get('filled',0))}/{int(r.get('quantity',0))}≈{float(r.get('gross',0))/1e6:.1f}M"
        for r in rows[:limit]
        if float(r.get("gross", 0) or 0) > 0
    )


def _dominant_type(itemq: dict[int, int]) -> int:
    if not itemq:
        return 0
    return int(max(itemq.items(), key=lambda kv: (int(kv[1]), -int(kv[0])))[0])


def _candidate_snapshot_rows(c, included_groups, requested_groups, snapshot: MarketSnapshot, previous_fingerprints):
    rows = []
    c_by_id = c.set_index("contract_id", drop=False)
    for cid, incq in included_groups.items():
        if cid not in c_by_id.index or not incq:
            continue
        cm = c_by_id.loc[cid]
        if isinstance(cm, pd.DataFrame):
            cm = cm.iloc[0]
        price = legacy.safe_num(cm.get("price"))
        reqq = requested_groups.get(cid, {})
        cash = _snapshot_partial(incq, snapshot.snapshot_buys)
        req = _snapshot_procure(reqq, snapshot.snapshot_sells) if reqq else {"complete": True, "cost": 0.0, "rows": []}
        preliminary_cost = price + (req["cost"] if req["complete"] else 0.0)
        snap_profit = cash["net_after_tax"] - preliminary_cost if req["complete"] else -math.inf
        snap_roi = snap_profit / preliminary_cost if preliminary_cost > 0 and math.isfinite(snap_profit) else -math.inf

        list_quote = _snapshot_procure(incq, snapshot.snapshot_sells)
        if list_quote["complete"] and list_quote["cost"] > 0:
            list_gross = float(list_quote["cost"])
            list_broker = list_gross * BROKER_FEE_RATE
            list_tax = list_gross * SALES_TAX_RATE
            list_relist = list_gross * RELIST_RESERVE_RATE
            snap_list_profit = list_gross - list_broker - list_tax - list_relist - price
            snap_list_base = price + list_broker + list_relist
            snap_list_roi = snap_list_profit / snap_list_base if snap_list_base > 0 else -math.inf
        else:
            list_gross = 0.0
            snap_list_profit = -math.inf
            snap_list_roi = -math.inf

        fp = contract_fingerprint(
            int(cid),
            price,
            incq,
            reqq,
            int(cm["start_location_id"]),
            str(cm.get("date_expired", "") or ""),
        )
        old_fp = previous_fingerprints.get(int(cid))
        change_priority = 2.0 if old_fp is None else (1.0 if old_fp != fp else 0.0)

        rows.append(
            {
                "contract_id": int(cid),
                "contract_price": price,
                "start_location_id": int(cm["start_location_id"]),
                "date_issued": cm.get("date_issued", ""),
                "date_expired": cm.get("date_expired", ""),
                "title": cm.get("title", ""),
                "included": incq,
                "requested": reqq,
                "snapshot_cash": cash,
                "snapshot_request": req,
                "snapshot_profit": snap_profit,
                "snapshot_roi": snap_roi,
                "snapshot_list_gross": list_gross,
                "snapshot_list_profit": snap_list_profit,
                "snapshot_list_roi": snap_list_roi,
                "change_priority": change_priority,
                "fingerprint": fp,
                "dominant_type_id": _dominant_type(incq),
                "has_requested": bool(reqq),
            }
        )
    return rows


def _decision_row(proof: ExecutionProof, decision, *, score: float = 0.0, legacy_fields: dict | None = None):
    row = {
        "engine_version": ENGINE_VERSION,
        **proof.to_dict(),
        "policy_stage": decision.stage,
        "execution_status": decision.execution_status,
        "confidence_class": decision.confidence_class,
        "mail_eligible": bool(decision.mail_eligible),
        "policy_reason": decision.reason,
        "opportunity_score": score,
        "score_grade": score_grade(score) if score else "",
    }
    if legacy_fields:
        row.update(legacy_fields)
    return row


def _score(proof: ExecutionProof, loc: dict, liquidity_score: float, hours: float, decision) -> float:
    status = "SAFE" if decision.stage in {"MAIL", "SAFE"} else "CHANGED"
    return opportunity_score(
        proof.net_profit,
        proof.net_roi,
        proof.profit_per_m3,
        liquidity_score,
        proof.stress_net_profit,
        loc.get("risk_rank", 5),
        hours,
        proof.market_change_pct,
        status,
    )


def _write_csv(path: Path, rows: list[dict]):
    pd.DataFrame(rows).to_csv(path, index=False)


def main():
    LATEST.mkdir(parents=True, exist_ok=True)
    STATE.mkdir(parents=True, exist_ok=True)
    cfg = PolicyConfig.from_env()
    funnel = RejectionFunnel()
    print(f"{ENGINE_VERSION}: broad discovery -> candidate pool -> ExecutionProof -> PolicyEngine")

    c_url, c_modified = latest_file(PUBLIC_CONTRACTS_INDEX)
    m_url, m_modified = latest_file(MARKET_ORDERS_INDEX)
    c_path, m_path = DATA / Path(c_url).name, DATA / Path(m_url).name
    if not c_path.exists():
        download(c_url, c_path)
    if not m_path.exists():
        download(m_url, m_path)

    contracts, items = load_contracts(c_path)
    funnel.stage("raw_contracts", len(contracts))
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
        c = c[exp.isna() | (exp > pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=legacy.MIN_HOURS_TO_EXPIRE))].copy()
    funnel.stage("eligible_contracts", len(c))

    valid = set(c["contract_id"].dropna().astype(int))
    ii = items[items["contract_id"].isin(valid)].copy()
    ii["contract_id"] = pd.to_numeric(ii["contract_id"], errors="coerce").astype("Int64")
    ii["_included"] = truthy_series(ii["is_included"])
    ii["_bpc"] = truthy_series(ii["is_blueprint_copy"])
    ii["quantity"] = pd.to_numeric(ii["quantity"], errors="coerce").fillna(0).astype(int)
    ii["type_id"] = pd.to_numeric(ii["type_id"], errors="coerce").fillna(0).astype(int)

    bpc_ids = set(ii.loc[ii["_bpc"], "contract_id"].dropna().astype(int))
    funnel.reject("BPC_ROUTED", len(bpc_ids))
    valid_no_bpc = valid - bpc_ids
    c = c[c["contract_id"].isin(valid_no_bpc)].copy()
    ii = ii[ii["contract_id"].isin(valid_no_bpc) & (ii["quantity"] > 0) & (ii["type_id"] > 0)].copy()

    included = ii[ii["_included"]].copy()
    requested = ii[~ii["_included"]].copy()
    included_groups, early_singletons = _prefilter_market_executable_groups(included)
    requested_groups = {int(cid): _aggregate(g) for cid, g in requested.groupby("contract_id", sort=False)}
    funnel.reject("MARKET_INELIGIBLE_SINGLETON", len(early_singletons))
    funnel.stage("market_executable_contracts", len(included_groups))

    orders = load_market_orders(m_path)
    snapshot_sells, snapshot_buys = prepare_jita_books(orders)
    del orders
    snapshot = MarketSnapshot(snapshot_buys=snapshot_buys, snapshot_sells=snapshot_sells)

    previous_fingerprints = load_fingerprints(FINGERPRINT_STATE)
    snapshot_rows = _candidate_snapshot_rows(
        c,
        included_groups,
        requested_groups,
        snapshot,
        previous_fingerprints,
    )
    save_fingerprints(FINGERPRINT_STATE, {int(r["contract_id"]): r["fingerprint"] for r in snapshot_rows})
    funnel.stage("snapshot_candidates", len(snapshot_rows))

    selected, pool_stats = select_candidate_pool(
        snapshot_rows,
        LIVE_LIMIT,
        metric_shares=(
            ("snapshot_profit", V3_PROFIT_SHARE),
            ("snapshot_roi", V3_ROI_SHARE),
            ("snapshot_list_profit", V3_LIST_PROFIT_SHARE),
            ("snapshot_list_roi", V3_LIST_ROI_SHARE),
            ("change_priority", V3_CHANGE_SHARE),
        ),
        newest_share=V3_NEWEST_SHARE,
        exploration_share=V3_EXPLORATION_SHARE,
        diversity_share=V3_DIVERSITY_SHARE,
        product_key="dominant_type_id",
        fill_metrics=("snapshot_profit", "snapshot_roi", "snapshot_list_profit", "snapshot_list_roi"),
        state_path=POOL_STATE,
        channel="v3-redesign-public",
    )
    selected_by_id = {int(x["contract_id"]): x for x in selected}
    for row in snapshot_rows:
        if row["has_requested"]:
            selected_by_id[int(row["contract_id"])] = row
    selected = list(selected_by_id.values())
    record_candidate_pool(POOL_STATE, "v3-redesign-public", selected)
    funnel.stage("candidate_pool", len(selected))

    if not selected:
        for path in (FULL_CASH_RESULT, CASH_RESULT, BARTER_RESULT, LIST_RESULT, RESEARCH_RESULT, ALL_RESULT):
            _write_csv(path, [])
        funnel.stage("mail_eligible", 0)
        funnel.write_json(FUNNEL_JSON)
        REPORT.write_text(funnel.markdown("Opportunity Engine V3 — no candidates"), "utf-8")
        return

    locations, _, _, _ = _resolve_locations(selected)
    before_location = len(selected)
    selected = [x for x in selected if _safe_location(locations.get(int(x["start_location_id"])))]
    funnel.reject("UNSAFE_OR_UNVERIFIED_LOCATION", before_location - len(selected))
    funnel.stage("location_executable", len(selected))

    all_tids = {
        int(tid)
        for p in selected
        for bundle in (p["included"], p["requested"])
        for tid in bundle
    }
    types, groups = _metadata(all_tids)

    feasible = []
    capital_removed = skin_removed = no_items = 0
    for p in selected:
        cid = int(p["contract_id"])
        raw_inc = included[included["contract_id"] == cid].to_dict("records")
        feasibility = analyze_contract_items(raw_inc, types, groups)
        if feasibility.has_highsec_restricted_ship:
            capital_removed += 1
            continue
        if not feasibility.adjusted_itemq:
            no_items += 1
            continue
        snap = _snapshot_partial(feasibility.adjusted_itemq, snapshot.snapshot_buys)
        gross = float(snap["gross"] or 0)
        skin_value = sum(
            float(r.get("gross", 0) or 0)
            for r in snap["rows"]
            if legacy.is_skin_related(int(r["type_id"]), types, groups)
        )
        if gross > 0 and skin_value / gross >= legacy.SKIN_MAJOR_SHARE:
            skin_removed += 1
            continue
        p = dict(p)
        p["included"] = feasibility.adjusted_itemq
        p["feasibility"] = feasibility
        feasible.append(p)

    funnel.reject("HIGHSEC_RESTRICTED_CAPITAL", capital_removed)
    funnel.reject("NO_EXECUTABLE_ITEMS", no_items)
    funnel.reject("SKIN_DOMINANT", skin_removed)
    funnel.stage("feasible", len(feasible))

    all_tids = {
        int(tid)
        for p in feasible
        for bundle in (p["included"], p["requested"])
        for tid in bundle
    }
    snapshot.live_buys, snapshot.failed_buy_types, snapshot.live_buy_at = fetch_live_jita_books(all_tids, "buy")
    snapshot.live_sells, snapshot.failed_sell_types, snapshot.live_sell_at = fetch_live_jita_books(all_tids, "sell")

    full_cash_rows = []
    cash_rows = []
    barter_rows = []
    list_rows = []
    research_rows = []
    listing_candidates = []

    for p in feasible:
        cid = int(p["contract_id"])
        loc = locations[int(p["start_location_id"])]
        included_q = p["included"]
        requested_q = p["requested"]
        cash = partial_liquidation(included_q, snapshot.live_buys, SALES_TAX_RATE)
        stress = _stress_partial(included_q, snapshot.live_buys)
        total_received_m3 = _volume(included_q, types)
        matched_m3 = _matched_volume(cash, types)
        haul_back = haul_reserve(total_received_m3, loc)
        change = material_change(float(p["snapshot_cash"].get("gross", 0) or 0), cash["gross"])

        if requested_q:
            fatal_sell = bool(set(requested_q).intersection(snapshot.failed_sell_types))
            req = procurement_cost(requested_q, snapshot.live_sells)
            stress_sell_books = {
                int(tid): drop_best_price_level(snapshot.live_sells.get(int(tid), []))
                for tid in requested_q
            }
            req_stress = procurement_cost(requested_q, stress_sell_books)
            if not req["complete"] or not req_stress["complete"]:
                funnel.reject("BARTER_PROCUREMENT_INCOMPLETE")
                research_rows.append({"contract_id": cid, "channel": "BARTER", "reason": "PROCUREMENT_INCOMPLETE"})
                continue

            req_m3 = _volume(requested_q, types)
            haul_out = haul_reserve(req_m3, loc)
            source_cost = p["contract_price"] + req["cost"]
            net_profit = cash["net_after_tax"] - source_cost - haul_out - haul_back
            invested = source_cost + haul_out + haul_back
            roi = net_profit / invested if invested > 0 else 0.0
            stress_profit = stress["net_after_tax"] - p["contract_price"] - req_stress["cost"] - haul_out - haul_back
            transport_m3 = req_m3 + total_received_m3
            density = profit_density(net_profit, transport_m3)
            proof = ExecutionProof(
                opportunity_id=str(cid),
                channel="BARTER",
                source_cost=source_cost,
                destination_value=cash["gross"],
                sales_tax=cash["sales_tax"],
                haul_cost=haul_out + haul_back,
                volume_m3=transport_m3,
                source_depth_complete=req["complete"],
                destination_depth_complete=cash["coverage"] >= 0.999999,
                access_verified=True,
                stress_value=stress["gross"],
                live_timestamp=max(snapshot.live_buy_at, snapshot.live_sell_at),
                coverage=cash["coverage"],
                net_profit=net_profit,
                net_roi=roi,
                stress_net_profit=stress_profit,
                profit_per_m3=density,
                market_change_pct=change,
                fatal=fatal_sell or bool(set(included_q).intersection(snapshot.failed_buy_types)) or cash["filled_units"] <= 0,
            )
            decision = evaluate_execution(proof, cfg)
            if decision.stage == "DANGER":
                funnel.reject(decision.reason)
                continue
            score = _score(proof, loc, 65.0, 0.5, decision) if decision.stage != "RESEARCH" else 0.0
            row = _decision_row(
                proof,
                decision,
                score=score,
                legacy_fields={
                    "contract_id": cid,
                    "contract_price": p["contract_price"],
                    "requested_purchase_cost": req["cost"],
                    "cash_floor_gross": cash["gross"],
                    "cash_floor_coverage": cash["coverage"],
                    "requested_volume_m3": req_m3,
                    "matched_return_volume_m3": matched_m3,
                    "received_total_volume_m3": total_received_m3,
                    "transport_volume_m3": transport_m3,
                    "haul_out_reserve": haul_out,
                    "haul_back_reserve": haul_back,
                    "snapshot_change_pct": change,
                    "receive_items": _row_items(included_q, types),
                    "provide_items": _row_items(requested_q, types),
                    "cash_items": _top_value_lines(cash, types),
                    "contract_title": p["title"],
                    "date_issued": p["date_issued"],
                    "date_expired": p["date_expired"],
                    "selection_reason": p.get("selection_reason", ""),
                    **loc,
                },
            )
            if decision.stage == "RESEARCH":
                research_rows.append(row)
            else:
                barter_rows.append(row)
            continue

        fatal_buy = bool(set(included_q).intersection(snapshot.failed_buy_types))
        net_profit = cash["net_after_tax"] - p["contract_price"] - haul_back
        invested = p["contract_price"] + haul_back
        roi = net_profit / invested if invested > 0 else 0.0
        stress_profit = stress["net_after_tax"] - p["contract_price"] - haul_back
        density = profit_density(net_profit, total_received_m3)
        full_cash = is_full_cash_exit(
            coverage=cash["coverage"],
            filled_units=cash["filled_units"],
            requested_units=cash["requested_units"],
        )
        channel = "FULL_CASH" if full_cash else "PARTIAL_CASH_FLOOR"
        proof = ExecutionProof(
            opportunity_id=str(cid),
            channel=channel,
            source_cost=p["contract_price"],
            destination_value=cash["gross"],
            sales_tax=cash["sales_tax"],
            haul_cost=haul_back,
            volume_m3=total_received_m3,
            source_depth_complete=True,
            destination_depth_complete=full_cash,
            access_verified=True,
            stress_value=stress["gross"],
            live_timestamp=snapshot.live_buy_at,
            coverage=cash["coverage"],
            net_profit=net_profit,
            net_roi=roi,
            stress_net_profit=stress_profit,
            profit_per_m3=density,
            market_change_pct=change,
            fatal=fatal_buy or cash["filled_units"] <= 0,
        )
        decision = evaluate_execution(proof, cfg)
        if decision.stage != "DANGER":
            score = _score(proof, loc, 70.0, 0.3, decision) if decision.stage != "RESEARCH" else 0.0
            row = _decision_row(
                proof,
                decision,
                score=score,
                legacy_fields={
                    "contract_id": cid,
                    "contract_price": p["contract_price"],
                    "net_profit": net_profit,
                    "net_roi": roi,
                    "stress_net_profit": stress_profit,
                    "cash_floor_gross": cash["gross"],
                    "sales_tax": cash["sales_tax"],
                    "cash_floor_coverage": cash["coverage"],
                    "cash_floor_filled_units": cash["filled_units"],
                    "bundle_total_units": cash["requested_units"],
                    "leftover_units_valued_zero": max(0, cash["requested_units"] - cash["filled_units"]),
                    "matched_volume_m3": matched_m3,
                    "total_volume_m3": total_received_m3,
                    "profit_per_m3": density,
                    "haul_reserve": haul_back,
                    "snapshot_change_pct": change,
                    "items": _row_items(included_q, types),
                    "cash_items": _top_value_lines(cash, types),
                    "contract_title": p["title"],
                    "date_issued": p["date_issued"],
                    "date_expired": p["date_expired"],
                    "selection_reason": p.get("selection_reason", ""),
                    **loc,
                },
            )
            if decision.stage in {"SAFE", "MAIL"}:
                if full_cash:
                    full_cash_rows.append(row)
                else:
                    cash_rows.append(row)
            else:
                # A weak immediate exit may still have supported listing value.
                # Defer its research row until listing evaluation finishes so one
                # contract has one final public route instead of duplicate channels.
                listing_candidates.append((p, loc, row))
        else:
            funnel.reject(decision.reason)

    listing_candidates.sort(
        key=lambda x: (
            float(x[0]["snapshot_list_profit"]) if math.isfinite(float(x[0]["snapshot_list_profit"])) else -math.inf,
            float(x[0]["snapshot_list_roi"]) if math.isfinite(float(x[0]["snapshot_list_roi"])) else -math.inf,
            float(x[0]["change_priority"]),
            str(x[0]["date_issued"]),
        ),
        reverse=True,
    )
    listing_candidates = listing_candidates[:LIST_HISTORY_LIMIT]
    listing_types = {int(tid) for p, _, _ in listing_candidates for tid in p["included"]}
    snapshot.history, snapshot.failed_history_types = fetch_market_history(listing_types)

    for p, loc, cash_research_row in listing_candidates:
        cid = int(p["contract_id"])
        itemq = p["included"]
        if set(itemq).intersection(snapshot.failed_sell_types) or set(itemq).intersection(snapshot.failed_history_types):
            funnel.reject("LIST_DATA_INCOMPLETE")
            research_rows.append(cash_research_row)
            continue
        q = conservative_listing_bundle(itemq, snapshot.live_sells, snapshot.history)
        if not q["complete"]:
            funnel.reject("LIST_UNSUPPORTED")
            research_rows.append(cash_research_row)
            continue
        if q["estimated_fill_days"] > LIST_MAX_FILL_DAYS:
            funnel.reject("LIST_TOO_SLOW")
            research_rows.append(cash_research_row)
            continue

        total_m3 = _volume(itemq, types)
        haul = haul_reserve(total_m3, loc)
        broker = q["gross"] * BROKER_FEE_RATE
        tax = q["gross"] * SALES_TAX_RATE
        relist = q["gross"] * RELIST_RESERVE_RATE
        net_profit = q["gross"] - broker - tax - relist - p["contract_price"] - haul
        invested = p["contract_price"] + haul + broker + relist
        roi = net_profit / invested if invested > 0 else 0.0
        stress_gross = q["gross"] * 0.95
        stress_profit = (
            stress_gross
            - stress_gross * (BROKER_FEE_RATE + SALES_TAX_RATE + RELIST_RESERVE_RATE)
            - p["contract_price"]
            - haul
        )
        density = profit_density(net_profit, total_m3)
        proof = ExecutionProof(
            opportunity_id=str(cid),
            channel="CONSERVATIVE_LIST",
            source_cost=p["contract_price"],
            destination_value=q["gross"],
            sales_tax=tax,
            broker_fee=broker,
            haul_cost=haul,
            other_cost=relist,
            volume_m3=total_m3,
            source_depth_complete=True,
            destination_depth_complete=False,
            access_verified=True,
            stress_value=stress_gross,
            live_timestamp=snapshot.live_sell_at,
            coverage=1.0,
            net_profit=net_profit,
            net_roi=roi,
            stress_net_profit=stress_profit,
            profit_per_m3=density,
        )
        decision = evaluate_listing(
            proof,
            cfg,
            max_fill_days=LIST_MAX_FILL_DAYS,
            estimated_fill_days=q["estimated_fill_days"],
        )
        if decision.stage == "DANGER":
            funnel.reject(decision.reason)
            continue
        liquidity_score = max(10.0, 100.0 - min(90.0, q["estimated_fill_days"] / LIST_MAX_FILL_DAYS * 90.0))
        score = _score(proof, loc, liquidity_score, max(0.5, q["estimated_fill_days"] * 24), decision) if decision.stage == "WATCH" else 0.0
        row = _decision_row(
            proof,
            decision,
            score=score,
            legacy_fields={
                "contract_id": cid,
                "contract_price": p["contract_price"],
                "conservative_gross": q["gross"],
                "broker_fee": broker,
                "sales_tax": tax,
                "relist_reserve": relist,
                "haul_reserve": haul,
                "net_profit": net_profit,
                "net_roi": roi,
                "stress_net_profit": stress_profit,
                "estimated_fill_days": q["estimated_fill_days"],
                "total_volume_m3": total_m3,
                "profit_per_m3": density,
                "items": _row_items(itemq, types),
                "contract_title": p["title"],
                "date_issued": p["date_issued"],
                "date_expired": p["date_expired"],
                "selection_reason": p.get("selection_reason", ""),
                **loc,
            },
        )
        if decision.stage == "RESEARCH":
            research_rows.append(row)
        else:
            list_rows.append(row)

    def rank_rows(rows):
        rows.sort(
            key=lambda x: (
                x.get("policy_stage") != "MAIL",
                x.get("policy_stage") != "SAFE",
                -float(x.get("opportunity_score", 0) or 0),
                -float(x.get("net_profit", 0) or 0),
            )
        )

    for rows in (full_cash_rows, cash_rows, barter_rows, list_rows):
        rank_rows(rows)

    all_rows = full_cash_rows + cash_rows + barter_rows + list_rows
    mail_count = sum(1 for r in all_rows if bool(r.get("mail_eligible")))
    funnel.stage("full_cash", len(full_cash_rows))
    funnel.stage("partial_cash_floor", len(cash_rows))
    funnel.stage("barter", len(barter_rows))
    funnel.stage("list_supported", len(list_rows))
    funnel.stage("research_watch", len(research_rows))
    funnel.stage("mail_eligible", mail_count)

    _write_csv(FULL_CASH_RESULT, full_cash_rows)
    _write_csv(CASH_RESULT, cash_rows)
    _write_csv(BARTER_RESULT, barter_rows)
    _write_csv(LIST_RESULT, list_rows)
    _write_csv(RESEARCH_RESULT, research_rows[:1000])
    _write_csv(ALL_RESULT, all_rows)
    funnel.write_json(FUNNEL_JSON)

    lines = [
        "# Opportunity Engine V3 — redesigned architecture",
        "",
        f"- Contracts snapshot: {c_modified}",
        f"- Market snapshot: {m_modified}",
        f"- Candidate universe: {len(snapshot_rows)}; deep validation pool: {len(selected)}; feasible: {len(feasible)}",
        f"- FULL_CASH: {len(full_cash_rows)}",
        f"- PARTIAL_CASH_FLOOR: {len(cash_rows)}",
        f"- BARTER: {len(barter_rows)}",
        f"- LIST-SUPPORTED: {len(list_rows)}",
        f"- RESEARCH: {len(research_rows)}",
        f"- FORMAL MAIL: {mail_count}",
        "",
        "Design rules:",
        "- Broad discovery is separate from final purchase recommendation.",
        "- Every deep candidate produces an ExecutionProof before policy classification.",
        "- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.",
        "- Listing valuation is WATCH-only and can never masquerade as locked cash.",
        "- Formal mail still requires the production profit/ROI/profit-density gate.",
        "- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.",
        "",
        funnel.markdown("Rejection Funnel"),
    ]
    REPORT.write_text("\n".join(lines).rstrip() + "\n", "utf-8")

    print(
        f"V3 redesign done: pool={len(selected)} full_cash={len(full_cash_rows)} "
        f"partial={len(cash_rows)} barter={len(barter_rows)} list={len(list_rows)} "
        f"research={len(research_rows)} mail={mail_count}; reasons={dict(funnel.reasons)}; "
        f"pool={pool_stats}"
    )


if __name__ == "__main__":
    main()
