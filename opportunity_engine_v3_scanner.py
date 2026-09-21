from __future__ import annotations

import json
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

import buy_only_contract_scanner as legacy
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
    score_grade,
)
from opportunity_engine_v3 import (
    BARTER_MIN_PROFIT,
    BARTER_MIN_ROI,
    CASH_FLOOR_MIN_PROFIT,
    CASH_FLOOR_MIN_ROI,
    LIST_MAX_FILL_DAYS,
    LIST_MIN_PROFIT,
    LIST_MIN_ROI,
    conservative_listing_bundle,
    diverse_candidates,
    fetch_live_jita_books,
    fetch_market_history,
    material_change,
    partial_liquidation,
    procurement_cost,
    v3_status,
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

LIVE_LIMIT = int(os.getenv("V3_PUBLIC_LIVE_LIMIT", "300"))
PER_METRIC = int(os.getenv("V3_PUBLIC_PER_METRIC", "110"))
NEWEST_COUNT = int(os.getenv("V3_PUBLIC_NEWEST_COUNT", "60"))
LIST_HISTORY_LIMIT = int(os.getenv("V3_LIST_HISTORY_LIMIT", "120"))

CASH_RESULT = LATEST / "v3_cash_floor.csv"
BARTER_RESULT = LATEST / "v3_barter.csv"
LIST_RESULT = LATEST / "v3_conservative_listing.csv"
REPORT = LATEST / "v3_public_opportunities.md"


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
        counts = {}
        all_one = {}
        for row in records:
            try:
                tid = int(row.get("type_id") or 0)
                qty = int(row.get("quantity") or 0)
            except Exception:
                continue
            if tid <= 0 or qty <= 0:
                continue
            counts[tid] = counts.get(tid, 0) + 1
            all_one[tid] = all_one.get(tid, True) and qty == 1
            raw = row.get("is_singleton", row.get("singleton", False))
            if str(raw or "").strip().lower() in {"1", "true", "t", "yes", "y"}:
                candidate_meta_tids.add(tid)
        for tid, n in counts.items():
            if n >= 2 and all_one.get(tid, False):
                candidate_meta_tids.add(tid)

    meta_types, meta_groups = _metadata(candidate_meta_tids) if candidate_meta_tids else ({}, {})
    grouped = {}
    excluded = {}
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


def _snapshot_partial(itemq, buy_books):
    q = partial_liquidation(itemq, buy_books, SALES_TAX_RATE)
    return q


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


def _safe_location(loc):
    if not loc:
        return False
    if int(float(loc.get("system_id", 0) or 0)) <= 0:
        return False
    if int(float(loc.get("shortest_jumps_to_jita", -1) or -1)) < 0:
        return False
    # Unknown/unfriendly player structures are deliberately fail-closed.
    if bool(loc.get("is_player_structure")) and not bool(loc.get("friendly_sov")) and not bool(loc.get("friendly_region")):
        return False
    return True


def _candidate_snapshot_rows(c, included_groups, requested_groups, buy_books, sell_books):
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
        cash = _snapshot_partial(incq, buy_books)
        req = _snapshot_procure(reqq, sell_books) if reqq else {"complete": True, "cost": 0.0, "rows": []}
        preliminary_cost = price + (req["cost"] if req["complete"] else 0.0)
        snap_profit = cash["net_after_tax"] - preliminary_cost if req["complete"] else -math.inf
        snap_roi = snap_profit / preliminary_cost if preliminary_cost > 0 and math.isfinite(snap_profit) else -math.inf

        # Separate sell-side prefilter. A contract can have weak buy orders yet still
        # be a strong conservative listing candidate, so it must not compete only on
        # the cash-floor metric.
        list_quote = _snapshot_procure(incq, sell_books)
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
                "has_requested": bool(reqq),
            }
        )
    return rows


def main():
    LATEST.mkdir(parents=True, exist_ok=True)
    print("Opportunity Engine V3: additive missed-opportunity scan")

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
        c = c[exp.isna() | (exp > pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=legacy.MIN_HOURS_TO_EXPIRE))].copy()

    valid = set(c["contract_id"].dropna().astype(int))
    ii = items[items["contract_id"].isin(valid)].copy()
    ii["contract_id"] = pd.to_numeric(ii["contract_id"], errors="coerce").astype("Int64")
    ii["_included"] = truthy_series(ii["is_included"])
    ii["_bpc"] = truthy_series(ii["is_blueprint_copy"])
    ii["quantity"] = pd.to_numeric(ii["quantity"], errors="coerce").fillna(0).astype(int)
    ii["type_id"] = pd.to_numeric(ii["type_id"], errors="coerce").fillna(0).astype(int)

    # Keep V3 public-contract logic separate from BPC logic. Any BPC in the contract
    # removes it here so blueprint valuation never leaks into cash-floor/barter math.
    bpc_ids = set(ii.loc[ii["_bpc"], "contract_id"].dropna().astype(int))
    valid_no_bpc = valid - bpc_ids
    c = c[c["contract_id"].isin(valid_no_bpc)].copy()
    ii = ii[ii["contract_id"].isin(valid_no_bpc) & (ii["quantity"] > 0) & (ii["type_id"] > 0)].copy()

    included = ii[ii["_included"]].copy()
    requested = ii[~ii["_included"]].copy()
    included_groups, early_singletons = _prefilter_market_executable_groups(included)
    requested_groups = {int(cid): _aggregate(g) for cid, g in requested.groupby("contract_id", sort=False)}
    early_singleton_qty = sum(sum(x.values()) for x in early_singletons.values())

    print(
        f"V3 contracts={len(c):,}; BPC-containing excluded={len(bpc_ids):,}; "
        f"barter={len(requested_groups):,}; market-ineligible singleton contracts={len(early_singletons):,} "
        f"qty={early_singleton_qty:,}"
    )

    orders = load_market_orders(m_path)
    snapshot_sells, snapshot_buys = prepare_jita_books(orders)
    del orders

    snapshot_rows = _candidate_snapshot_rows(c, included_groups, requested_groups, snapshot_buys, snapshot_sells)
    # Do not require snapshot profitability. The diverse union intentionally includes
    # recent/near-threshold contracts so a fresh live order can create an opportunity.
    selected = diverse_candidates(
        snapshot_rows,
        total_limit=LIVE_LIMIT,
        per_metric=PER_METRIC,
        metrics=("snapshot_profit", "snapshot_roi", "snapshot_list_profit", "snapshot_list_roi"),
        newest_count=NEWEST_COUNT,
    )
    # Barter contracts are rare. Include every one instead of forcing them to win a
    # ranking contest against tens of thousands of normal item-exchange contracts.
    selected_by_id = {int(x["contract_id"]): x for x in selected}
    for row in snapshot_rows:
        if row["has_requested"]:
            selected_by_id[int(row["contract_id"])] = row
    selected = list(selected_by_id.values())
    print(f"V3 live public-contract pool={len(selected)} (including all barter contracts)")

    if not selected:
        for path in (CASH_RESULT, BARTER_RESULT, LIST_RESULT):
            pd.DataFrame().to_csv(path, index=False)
        REPORT.write_text("# Opportunity Engine V3\n\nNo candidates.\n", encoding="utf-8")
        return

    locations, own_aid, own_name, own_ticker = _resolve_locations(selected)
    selected = [x for x in selected if _safe_location(locations.get(int(x["start_location_id"])))]
    all_tids = {
        int(tid)
        for p in selected
        for bundle in (p["included"], p["requested"])
        for tid in bundle
    }
    types, groups = _metadata(all_tids)

    feasible = []
    skin_removed = capital_removed = singleton_adjusted = 0
    for p in selected:
        cid = int(p["contract_id"])
        raw_inc = included[included["contract_id"] == cid].to_dict("records")
        f = analyze_contract_items(raw_inc, types, groups)
        if f.has_highsec_restricted_ship:
            capital_removed += 1
            continue
        if not f.adjusted_itemq:
            continue
        if f.excluded_market_singletons:
            singleton_adjusted += 1
        # SKIN-heavy bundles remain excluded from automated recommendations.
        snap = _snapshot_partial(f.adjusted_itemq, snapshot_buys)
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
        p["included"] = f.adjusted_itemq
        p["feasibility"] = f
        p["excluded_market_singleton_types"] = len(f.excluded_market_singletons)
        p["excluded_market_singleton_qty"] = sum(f.excluded_market_singletons.values())
        feasible.append(p)

    print(
        f"V3 feasible={len(feasible)} capital_removed={capital_removed} "
        f"skin_removed={skin_removed} singleton_adjusted={singleton_adjusted}"
    )
    all_tids = {
        int(tid)
        for p in feasible
        for bundle in (p["included"], p["requested"])
        for tid in bundle
    }
    live_buys, failed_buy, live_at_buy = fetch_live_jita_books(all_tids, "buy")
    live_sells, failed_sell, live_at_sell = fetch_live_jita_books(all_tids, "sell")

    cash_rows, barter_rows = [], []
    listing_candidates = []
    for p in feasible:
        cid = int(p["contract_id"])
        loc = locations[int(p["start_location_id"])]
        included_q = p["included"]
        requested_q = p["requested"]
        fatal_buy = bool(set(included_q).intersection(failed_buy))
        cash = partial_liquidation(included_q, live_buys, SALES_TAX_RATE)
        stress = _stress_partial(included_q, live_buys)

        # Only haul the units used by the cash-floor proof. Leftovers remain worth zero
        # and need not be transported merely to justify the opportunity.
        matched_m3 = _matched_volume(cash, types)
        haul_back = haul_reserve(matched_m3, loc)
        snapshot_cash_gross = float(p["snapshot_cash"].get("gross", 0) or 0)
        change = material_change(snapshot_cash_gross, cash["gross"])

        if not requested_q:
            profit = cash["net_after_tax"] - p["contract_price"] - haul_back
            invested = p["contract_price"] + haul_back
            roi = profit / invested if invested > 0 else 0.0
            stress_profit = stress["net_after_tax"] - p["contract_price"] - haul_back
            status = v3_status(
                profit, roi, stress_profit,
                CASH_FLOOR_MIN_PROFIT, CASH_FLOOR_MIN_ROI,
                change_pct=change,
                fatal=fatal_buy or cash["filled_units"] <= 0,
            )
            if status != "DANGER":
                density = profit / matched_m3 if matched_m3 > 0 else profit
                score = opportunity_score(
                    profit, roi, density, 70.0, stress_profit,
                    loc.get("risk_rank", 5), 0.3, change, status,
                )
                cash_rows.append(
                    {
                        "engine_version": "Opportunity Engine V3",
                        "channel": "CASH_FLOOR",
                        "execution_status": status,
                        "score_grade": score_grade(score),
                        "opportunity_score": score,
                        "contract_id": cid,
                        "contract_price": p["contract_price"],
                        "net_profit": profit,
                        "net_roi": roi,
                        "stress_net_profit": stress_profit,
                        "cash_floor_gross": cash["gross"],
                        "sales_tax": cash["sales_tax"],
                        "cash_floor_coverage": cash["coverage"],
                        "cash_floor_filled_units": cash["filled_units"],
                        "bundle_total_units": cash["requested_units"],
                        "leftover_units_valued_zero": max(0, cash["requested_units"] - cash["filled_units"]),
                        "matched_volume_m3": matched_m3,
                        "haul_reserve": haul_back,
                        "snapshot_change_pct": change,
                        "items": _row_items(included_q, types),
                        "cash_items": _top_value_lines(cash, types),
                        "contract_title": p["title"],
                        "date_issued": p["date_issued"],
                        "date_expired": p["date_expired"],
                        "live_revalidated_at": live_at_buy,
                        **loc,
                    }
                )
        else:
            fatal_sell = bool(set(requested_q).intersection(failed_sell))
            req = procurement_cost(requested_q, live_sells)
            req_stress_books = {int(tid): drop_best_price_level(live_sells.get(int(tid), [])) for tid in requested_q}
            # For asks, dropping the best level makes procurement more expensive.
            req_stress = procurement_cost(requested_q, req_stress_books)
            req_m3 = _volume(requested_q, types)
            haul_out = haul_reserve(req_m3, loc)
            if req["complete"] and req_stress["complete"]:
                profit = cash["net_after_tax"] - p["contract_price"] - req["cost"] - haul_out - haul_back
                invested = p["contract_price"] + req["cost"] + haul_out + haul_back
                roi = profit / invested if invested > 0 else 0.0
                stress_profit = (
                    stress["net_after_tax"] - p["contract_price"] - req_stress["cost"] - haul_out - haul_back
                )
                status = v3_status(
                    profit, roi, stress_profit,
                    BARTER_MIN_PROFIT, BARTER_MIN_ROI,
                    change_pct=change,
                    fatal=fatal_buy or fatal_sell or cash["filled_units"] <= 0,
                )
                if status != "DANGER":
                    density = profit / max(1.0, req_m3 + matched_m3)
                    score = opportunity_score(
                        profit, roi, density, 65.0, stress_profit,
                        loc.get("risk_rank", 5), 0.5, change, status,
                    )
                    barter_rows.append(
                        {
                            "engine_version": "Opportunity Engine V3",
                            "channel": "BARTER",
                            "execution_status": status,
                            "score_grade": score_grade(score),
                            "opportunity_score": score,
                            "contract_id": cid,
                            "contract_price": p["contract_price"],
                            "requested_purchase_cost": req["cost"],
                            "net_profit": profit,
                            "net_roi": roi,
                            "stress_net_profit": stress_profit,
                            "cash_floor_gross": cash["gross"],
                            "sales_tax": cash["sales_tax"],
                            "cash_floor_coverage": cash["coverage"],
                            "requested_volume_m3": req_m3,
                            "matched_return_volume_m3": matched_m3,
                            "haul_out_reserve": haul_out,
                            "haul_back_reserve": haul_back,
                            "snapshot_change_pct": change,
                            "receive_items": _row_items(included_q, types),
                            "provide_items": _row_items(requested_q, types),
                            "cash_items": _top_value_lines(cash, types),
                            "contract_title": p["title"],
                            "date_issued": p["date_issued"],
                            "date_expired": p["date_expired"],
                            "live_revalidated_at": max(live_at_buy, live_at_sell),
                            **loc,
                        }
                    )

        # Conservative sell-order channel is intentionally limited to pure item
        # contracts with no requested inputs. It is evaluated later with history.
        if not requested_q:
            listing_candidates.append((p, loc))

    # Listing candidates rank on their own sell-side snapshot economics, not on
    # buy-order cash-floor economics.
    listing_candidates.sort(
        key=lambda x: (
            float(x[0]["snapshot_list_profit"]) if math.isfinite(float(x[0]["snapshot_list_profit"])) else -math.inf,
            float(x[0]["snapshot_list_roi"]) if math.isfinite(float(x[0]["snapshot_list_roi"])) else -math.inf,
            str(x[0]["date_issued"]),
        ),
        reverse=True,
    )
    listing_candidates = listing_candidates[:LIST_HISTORY_LIMIT]
    listing_types = {int(tid) for p, _ in listing_candidates for tid in p["included"]}
    history, history_failed = fetch_market_history(listing_types)

    list_rows = []
    for p, loc in listing_candidates:
        itemq = p["included"]
        if set(itemq).intersection(failed_sell) or set(itemq).intersection(history_failed):
            continue
        q = conservative_listing_bundle(itemq, live_sells, history)
        if not q["complete"] or q["estimated_fill_days"] > LIST_MAX_FILL_DAYS:
            continue
        total_m3 = _volume(itemq, types)
        haul = haul_reserve(total_m3, loc)
        broker = q["gross"] * BROKER_FEE_RATE
        tax = q["gross"] * SALES_TAX_RATE
        relist = q["gross"] * RELIST_RESERVE_RATE
        profit = q["gross"] - broker - tax - relist - p["contract_price"] - haul
        invested = p["contract_price"] + haul + broker + relist
        roi = profit / invested if invested > 0 else 0.0

        # Extra 5% price shock across the already-haircut conservative valuation.
        stress_gross = q["gross"] * 0.95
        stress_profit = stress_gross - stress_gross * (BROKER_FEE_RATE + SALES_TAX_RATE + RELIST_RESERVE_RATE) - p["contract_price"] - haul
        status = v3_status(
            profit, roi, stress_profit,
            LIST_MIN_PROFIT, LIST_MIN_ROI,
            change_pct=0.0,
            fatal=False,
        )
        if status == "DANGER":
            continue
        density = profit / total_m3 if total_m3 > 0 else profit
        liquidity_score = max(10.0, 100.0 - min(90.0, q["estimated_fill_days"] / LIST_MAX_FILL_DAYS * 90.0))
        score = opportunity_score(
            profit, roi, density, liquidity_score, stress_profit,
            loc.get("risk_rank", 5), max(0.5, q["estimated_fill_days"] * 24), 0.0, status,
        )
        list_rows.append(
            {
                "engine_version": "Opportunity Engine V3",
                "channel": "CONSERVATIVE_LIST",
                "execution_status": status,
                "score_grade": score_grade(score),
                "opportunity_score": score,
                "contract_id": int(p["contract_id"]),
                "contract_price": p["contract_price"],
                "conservative_gross": q["gross"],
                "broker_fee": broker,
                "sales_tax": tax,
                "relist_reserve": relist,
                "haul_reserve": haul,
                "net_profit": profit,
                "net_roi": roi,
                "stress_net_profit": stress_profit,
                "estimated_fill_days": q["estimated_fill_days"],
                "total_volume_m3": total_m3,
                "items": _row_items(itemq, types),
                "contract_title": p["title"],
                "date_issued": p["date_issued"],
                "date_expired": p["date_expired"],
                "live_revalidated_at": live_at_sell,
                **loc,
            }
        )

    cash_rows.sort(key=lambda x: (x["execution_status"] != "SAFE", -x["opportunity_score"], -x["net_profit"]))
    barter_rows.sort(key=lambda x: (x["execution_status"] != "SAFE", -x["opportunity_score"], -x["net_profit"]))
    list_rows.sort(key=lambda x: (x["execution_status"] != "SAFE", -x["opportunity_score"], -x["net_profit"]))

    pd.DataFrame(cash_rows).to_csv(CASH_RESULT, index=False)
    pd.DataFrame(barter_rows).to_csv(BARTER_RESULT, index=False)
    pd.DataFrame(list_rows).to_csv(LIST_RESULT, index=False)

    lines = [
        "# Opportunity Engine V3 — missed-opportunity channels",
        "",
        f"- Contracts snapshot: `{c_modified}`",
        f"- Market snapshot: `{m_modified}`",
        f"- Live pool: `{len(selected)}`; feasible: `{len(feasible)}`",
        f"- CASH_FLOOR: `{len(cash_rows)}`",
        f"- BARTER: `{len(barter_rows)}`",
        f"- CONSERVATIVE_LIST: `{len(list_rows)}`",
        "",
        "V3 is additive. Existing V2 SAFE channels are unchanged.",
        "Cash-floor leftovers are explicitly valued at zero.",
        "Barter requires complete live Jita procurement depth for all requested inputs.",
        "Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"V3 public done: cash={len(cash_rows)} barter={len(barter_rows)} "
        f"list={len(list_rows)}"
    )


if __name__ == "__main__":
    main()
