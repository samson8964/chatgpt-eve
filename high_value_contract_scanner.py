from __future__ import annotations

import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

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
    ESI,
    HIGHSEC_RESTRICTED_GROUP_IDS,
    aggregate_market_executable_items,
    analyze_contract_items,
    drop_best_price_level,
    opportunity_score,
    score_grade,
)
from opportunity_engine_v3 import (
    conservative_listing_bundle,
    fetch_live_jita_books,
    fetch_market_history,
    partial_liquidation,
    procurement_cost,
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

UA = "chatgpt-eve-high-value-contracts/1.0"
WORKERS = int(os.getenv("HVC_WORKERS", "12"))
HTTP_TIMEOUT = int(os.getenv("HVC_HTTP_TIMEOUT", "35"))

MIN_PRICE = float(os.getenv("HVC_MIN_CONTRACT_PRICE", "5000000000"))
ACTIONABLE_CAPITAL = float(os.getenv("HVC_ACTIONABLE_CAPITAL", "8000000000"))
WATCH_MAX = float(os.getenv("HVC_WATCH_MAX", "20000000000"))
MIN_TYPES = int(os.getenv("HVC_MIN_TYPES", "2"))
MIN_HOURS_TO_EXPIRE = float(os.getenv("HVC_MIN_HOURS_TO_EXPIRE", "0.5"))

ACTIONABLE_LIVE_LIMIT = int(os.getenv("HVC_ACTIONABLE_LIVE_LIMIT", "160"))
WATCH_LIVE_LIMIT = int(os.getenv("HVC_WATCH_LIVE_LIMIT", "50"))
RESEARCH_LIVE_LIMIT = int(os.getenv("HVC_RESEARCH_LIVE_LIMIT", "20"))
HISTORY_CANDIDATES = int(os.getenv("HVC_HISTORY_CANDIDATES", "70"))

MIN_PROFIT = float(os.getenv("HVC_MIN_NET_PROFIT", "500000000"))
MIN_ROI = float(os.getenv("HVC_MIN_NET_ROI", "0.10"))
LIST_MAX_FILL_DAYS = float(os.getenv("HVC_LIST_MAX_FILL_DAYS", "14"))
LIST_HAIRCUT = float(os.getenv("HVC_LIST_PRICE_HAIRCUT", "0.10"))
LIST_PARTICIPATION = float(os.getenv("HVC_LIST_PARTICIPATION", "0.20"))
CAPITAL_LOCAL_RISK_RATE = float(os.getenv("HVC_CAPITAL_LOCAL_RISK_RATE", "0.03"))
STRESS_PRICE_SHOCK = float(os.getenv("HVC_STRESS_PRICE_SHOCK", "0.05"))
MAX_LIVE_TYPES_PER_CONTRACT = int(os.getenv("HVC_MAX_LIVE_TYPES_PER_CONTRACT", "25"))
SKIN_MAJOR_SHARE = float(os.getenv("DEAL_SKIN_MAJOR_SHARE", "0.50"))

UNIVERSE_RESULT = LATEST / "high_value_contract_universe.csv"
ALL_RESULT = LATEST / "high_value_contract_all.csv"
ACTIONABLE_RESULT = LATEST / "high_value_contract_actionable.csv"
WATCH_RESULT = LATEST / "high_value_contract_watch.csv"
REPORT = LATEST / "high_value_contract_report.md"


def num(value, default=0.0):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def truthy(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "t", "yes", "y"}


def metadata(type_ids):
    types = fetch_many_ref("types", type_ids)
    gids = {type_group_id(v) for v in types.values()}
    gids.discard(None)
    return types, fetch_many_ref("groups", gids)


def prefilter_groups(df):
    if df.empty:
        return {}, {}
    candidate_meta_tids = set()
    for _, g in df.groupby("contract_id", sort=False):
        unit_counts = {}
        for row in g.to_dict("records"):
            tid = int(row.get("type_id") or 0)
            qty = int(row.get("quantity") or 0)
            if tid <= 0 or qty <= 0:
                continue
            if qty == 1:
                unit_counts[tid] = unit_counts.get(tid, 0) + 1
            if truthy(row.get("is_singleton", row.get("singleton", False))):
                candidate_meta_tids.add(tid)
        for tid, count in unit_counts.items():
            if count >= 2:
                candidate_meta_tids.add(tid)

    mt, mg = metadata(candidate_meta_tids) if candidate_meta_tids else ({}, {})
    grouped, excluded = {}, {}
    for cid, g in df.groupby("contract_id", sort=False):
        q, ex = aggregate_market_executable_items(g.to_dict("records"), mt, mg)
        if q:
            grouped[int(cid)] = q
        if ex:
            excluded[int(cid)] = ex
    return grouped, excluded


def volume(itemq, types):
    return sum(max(0.0, type_volume(types.get(int(tid)))) * int(qty) for tid, qty in itemq.items())


def group_name(obj):
    if not obj:
        return ""
    n = obj.get("name")
    if isinstance(n, dict):
        return str(n.get("en") or n.get("zh") or next(iter(n.values()), ""))
    return str(n or obj.get("name_en") or "")


def restricted_ship(tid, types, groups):
    tobj = types.get(int(tid)) or {}
    gid = int(type_group_id(tobj) or 0)
    if gid in HIGHSEC_RESTRICTED_GROUP_IDS:
        return True
    g = group_name(groups.get(gid)).lower()
    return any(k in g for k in (
        "titan", "dreadnought", "carrier", "supercarrier",
        "force auxiliary", "capital industrial ship", "lancer dreadnought",
    ))


def split_capitals(itemq, types, groups):
    normal, capital = {}, {}
    for tid, qty in itemq.items():
        (capital if restricted_ship(tid, types, groups) else normal)[int(tid)] = int(qty)
    return normal, capital


def focus_normal_bundle(itemq, buy_books, sell_books):
    """Keep only the largest snapshot-value normal types for live validation.

    Omitted items are worth zero in final economics, so this can only understate
    value. Full contract volume is still charged to hauling separately.
    """
    if len(itemq) <= MAX_LIVE_TYPES_PER_CONTRACT:
        return dict(itemq)
    ranked = []
    for tid, qty in itemq.items():
        cash = partial_liquidation({int(tid): int(qty)}, buy_books, SALES_TAX_RATE)
        replacement = procurement_cost({int(tid): int(qty)}, sell_books)
        sell_value = float(replacement["cost"]) if replacement.get("complete") else 0.0
        score = max(float(cash.get("net_after_tax", 0) or 0), sell_value)
        ranked.append((score, int(tid), int(qty)))
    ranked.sort(reverse=True)
    return {tid: qty for _, tid, qty in ranked[:MAX_LIVE_TYPES_PER_CONTRACT]}


def tier(price):
    if price <= ACTIONABLE_CAPITAL:
        return "ACTIONABLE"
    if price <= WATCH_MAX:
        return "WATCH"
    return "RESEARCH"


def pick_tier(rows, bucket, limit):
    pool = [r for r in rows if r["capital_bucket"] == bucket]
    if len(pool) <= limit:
        return pool
    selected = {}
    edge_n = max(1, int(limit * 0.60))
    newest_n = max(1, limit - edge_n)
    for r in sorted(pool, key=lambda x: (x["snapshot_best_edge"], x["snapshot_roi"]), reverse=True)[:edge_n]:
        selected[int(r["contract_id"])] = r
    for r in sorted(pool, key=lambda x: str(x.get("date_issued", "")), reverse=True)[:newest_n]:
        selected[int(r["contract_id"])] = r
    return list(selected.values())[:limit]


def safe_location(loc):
    if not loc or int(num(loc.get("system_id"), 0)) <= 0:
        return False
    if int(num(loc.get("shortest_jumps_to_jita"), -1)) < 0:
        return False
    if bool(loc.get("is_player_structure")) and not bool(loc.get("friendly_sov")) and not bool(loc.get("friendly_region")):
        return False
    return True


def resolve_locations(candidates):
    friendly, aid, aname, aticker = current_friendly_alliances()
    sov = sovereignty_owners()
    lids = sorted({int(x["start_location_id"]) for x in candidates})
    structures = load_structures([x for x in lids if x >= 1_000_000_000_000])
    out = {}
    with ThreadPoolExecutor(max_workers=min(WORKERS, max(1, len(lids)))) as ex:
        futs = {ex.submit(resolve_location, lid, structures, friendly, sov): lid for lid in lids}
        for fut in as_completed(futs):
            lid = futs[fut]
            try:
                out[lid] = fut.result()
            except Exception:
                out[lid] = None
    return out, aid, aname, aticker


def get_json(url, params=None, tries=4):
    last = None
    for attempt in range(tries):
        try:
            r = requests.get(
                url,
                params=params,
                headers={"User-Agent": UA, "Accept": "application/json"},
                timeout=HTTP_TIMEOUT,
            )
            if r.status_code in {420, 429, 500, 502, 503, 504} and attempt + 1 < tries:
                time.sleep(0.8 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json(), r.headers
        except Exception as exc:
            last = exc
            if attempt + 1 < tries:
                time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"ESI request failed: {url}: {last}")


def fetch_region_buy(region_id, type_id):
    rows, page = [], 1
    try:
        while True:
            payload, headers = get_json(
                f"{ESI}/markets/{int(region_id)}/orders/",
                {
                    "datasource": "tranquility",
                    "order_type": "buy",
                    "type_id": int(type_id),
                    "page": page,
                },
            )
            for row in payload or []:
                if not truthy(row.get("is_buy_order", True)):
                    continue
                vol = int(row.get("volume_remain") or 0)
                price = num(row.get("price"), 0.0)
                if vol > 0 and price > 0:
                    rows.append({
                        "price": price,
                        "vol": vol,
                        "min": max(1, int(row.get("min_volume") or 1)),
                        "order_id": int(row.get("order_id") or 0),
                    })
            pages = max(1, int(headers.get("X-Pages", "1") or 1))
            if page >= pages:
                break
            page += 1
        rows.sort(key=lambda x: (x["price"], x["order_id"]), reverse=True)
        return (int(region_id), int(type_id)), rows, None
    except Exception as exc:
        return (int(region_id), int(type_id)), [], str(exc)


def fetch_region_buys(pairs):
    out, failed = {}, set()
    pairs = sorted({(int(r), int(t)) for r, t in pairs if int(r) > 0 and int(t) > 0})
    if not pairs:
        return out, failed
    with ThreadPoolExecutor(max_workers=min(WORKERS, len(pairs))) as ex:
        futs = {ex.submit(fetch_region_buy, rid, tid): (rid, tid) for rid, tid in pairs}
        for fut in as_completed(futs):
            pair = futs[fut]
            try:
                key, book, err = fut.result()
            except Exception:
                failed.add(pair)
                continue
            out[key] = book
            if err:
                failed.add(key)
    return out, failed


def empty_cash():
    return {
        "gross": 0.0, "sales_tax": 0.0, "net_after_tax": 0.0,
        "requested_units": 0, "filled_units": 0, "coverage": 1.0,
        "matched_itemq": {}, "rows": [],
    }


def cash_quote(itemq, books):
    return partial_liquidation(itemq, books, SALES_TAX_RATE) if itemq else empty_cash()


def stress_cash(itemq, books):
    if not itemq:
        return empty_cash()
    stressed = {int(tid): drop_best_price_level(books.get(int(tid), [])) for tid in itemq}
    return partial_liquidation(itemq, stressed, SALES_TAX_RATE)


def listing_net(gross):
    broker = gross * BROKER_FEE_RATE
    tax = gross * SALES_TAX_RATE
    relist = gross * RELIST_RESERVE_RATE
    return gross - broker - tax - relist


def items_text(itemq, types, limit=14):
    return " | ".join(
        f"{name_en(types.get(int(tid)), str(tid))} x{int(qty)}"
        for tid, qty in sorted(itemq.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    )


def top_cash_items(quote, types, limit=10):
    rows = sorted(quote.get("rows", []), key=lambda r: num(r.get("gross"), 0.0), reverse=True)
    out = []
    for row in rows[:limit]:
        gross = num(row.get("gross"), 0.0)
        if gross <= 0:
            continue
        tid = int(row["type_id"])
        out.append(
            f"{name_en(types.get(tid), str(tid))} "
            f"{int(row.get('filled',0))}/{int(row.get('quantity',0))}≈{gross/1e9:.2f}B"
        )
    return " | ".join(out)


def write_empty(message):
    for path in (UNIVERSE_RESULT, ALL_RESULT, ACTIONABLE_RESULT, WATCH_RESULT):
        pd.DataFrame().to_csv(path, index=False)
    REPORT.write_text("# High Value Contract Engine\n\n" + message + "\n", encoding="utf-8")


def main():
    LATEST.mkdir(parents=True, exist_ok=True)
    print("High Value Contract Engine: independent >5B asset-bundle scan")

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
        & (contracts["price"] > MIN_PRICE)
        & contracts["start_location_id"].notna()
    ].copy()
    if "date_expired" in c.columns:
        exp = pd.to_datetime(c["date_expired"], utc=True, errors="coerce")
        c = c[exp.isna() | (exp > pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=MIN_HOURS_TO_EXPIRE))].copy()

    if c.empty:
        write_empty("No active contracts above the high-value floor.")
        return

    valid = set(c["contract_id"].dropna().astype(int))
    ii = items[items["contract_id"].isin(valid)].copy()
    ii["contract_id"] = pd.to_numeric(ii["contract_id"], errors="coerce").astype("Int64")
    ii["_included"] = truthy_series(ii["is_included"])
    ii["_bpc"] = truthy_series(ii["is_blueprint_copy"])
    ii["quantity"] = pd.to_numeric(ii["quantity"], errors="coerce").fillna(0).astype(int)
    ii["type_id"] = pd.to_numeric(ii["type_id"], errors="coerce").fillna(0).astype(int)

    bpc_ids = set(ii.loc[ii["_bpc"], "contract_id"].dropna().astype(int))
    requested_ids = set(ii.loc[~ii["_included"], "contract_id"].dropna().astype(int))
    usable = valid - bpc_ids - requested_ids

    included = ii[
        ii["contract_id"].isin(usable)
        & ii["_included"]
        & (ii["quantity"] > 0)
        & (ii["type_id"] > 0)
    ].copy()
    raw_groups = {int(cid): g.to_dict("records") for cid, g in included.groupby("contract_id", sort=False)}
    grouped, early_singletons = prefilter_groups(included)
    grouped = {cid: q for cid, q in grouped.items() if len(q) >= MIN_TYPES}
    c = c[c["contract_id"].isin(grouped)].copy()

    print(
        f"HVC active>{MIN_PRICE/1e9:.1f}B={len(valid):,}; "
        f"BPC excluded={len(bpc_ids):,}; barter excluded={len(requested_ids):,}; "
        f"multi eligible={len(grouped):,}"
    )
    if c.empty:
        write_empty("No eligible pure multi-item high-value contracts.")
        return

    orders = load_market_orders(m_path)
    snapshot_sells, snapshot_buys = prepare_jita_books(orders)
    del orders

    c_by_id = c.set_index("contract_id", drop=False)
    coarse = []
    for cid, itemq in grouped.items():
        cm = c_by_id.loc[cid]
        if isinstance(cm, pd.DataFrame):
            cm = cm.iloc[0]
        price = num(cm.get("price"), 0.0)
        cash = partial_liquidation(itemq, snapshot_buys, SALES_TAX_RATE)
        replacement = procurement_cost(itemq, snapshot_sells)
        cash_profit = cash["net_after_tax"] - price
        cash_roi = cash_profit / price if price > 0 else -math.inf
        if replacement["complete"] and replacement["cost"] > 0:
            list_profit = listing_net(float(replacement["cost"])) - price
            list_roi = list_profit / price if price > 0 else -math.inf
        else:
            list_profit, list_roi = -math.inf, -math.inf
        best_edge = max(cash_profit, list_profit)
        best_roi = max(cash_roi, list_roi)
        coarse.append({
            "contract_id": int(cid),
            "contract_price": price,
            "capital_bucket": tier(price),
            "start_location_id": int(cm["start_location_id"]),
            "date_issued": cm.get("date_issued", ""),
            "date_expired": cm.get("date_expired", ""),
            "contract_title": cm.get("title", ""),
            "item_type_count": len(itemq),
            "item_total_units": sum(itemq.values()),
            "snapshot_cash_profit": cash_profit,
            "snapshot_cash_coverage": cash["coverage"],
            "snapshot_list_profit": list_profit if math.isfinite(list_profit) else 0.0,
            "snapshot_best_edge": best_edge if math.isfinite(best_edge) else -1e30,
            "snapshot_roi": best_roi if math.isfinite(best_roi) else -1e30,
        })

    universe = pd.DataFrame(coarse)
    universe.sort_values(["capital_bucket", "snapshot_best_edge"], ascending=[True, False], inplace=True)
    universe.to_csv(UNIVERSE_RESULT, index=False)

    selected = (
        pick_tier(coarse, "ACTIONABLE", ACTIONABLE_LIVE_LIMIT)
        + pick_tier(coarse, "WATCH", WATCH_LIVE_LIMIT)
        + pick_tier(coarse, "RESEARCH", RESEARCH_LIVE_LIMIT)
    )
    selected = list({int(x["contract_id"]): x for x in selected}.values())
    print(
        f"HVC coarse universe={len(coarse):,}; deep pool={len(selected):,}; "
        f"actionable={sum(x['capital_bucket']=='ACTIONABLE' for x in selected)}, "
        f"watch={sum(x['capital_bucket']=='WATCH' for x in selected)}, "
        f"research={sum(x['capital_bucket']=='RESEARCH' for x in selected)}"
    )

    locations, own_aid, own_name, own_ticker = resolve_locations(selected)
    selected = [x for x in selected if safe_location(locations.get(int(x["start_location_id"])))]
    if not selected:
        write_empty("No reachable high-value deep candidates.")
        return

    all_tids = {int(tid) for p in selected for tid in grouped.get(int(p["contract_id"]), {})}
    types, groups = metadata(all_tids)

    feasible = []
    for p in selected:
        cid = int(p["contract_id"])
        f = analyze_contract_items(raw_groups.get(cid, []), types, groups)
        if not f.adjusted_itemq or len(f.adjusted_itemq) < MIN_TYPES:
            continue
        all_normal_q, capital_q = split_capitals(f.adjusted_itemq, types, groups)
        normal_q = focus_normal_bundle(all_normal_q, snapshot_buys, snapshot_sells)
        snap = partial_liquidation(normal_q, snapshot_buys, SALES_TAX_RATE) if normal_q else empty_cash()
        skin_value = sum(
            num(r.get("gross"), 0.0)
            for r in snap.get("rows", [])
            if legacy.is_skin_related(int(r["type_id"]), types, groups)
        )
        skin_share = skin_value / snap["gross"] if snap["gross"] > 0 else 0.0
        q = dict(p)
        q["normal_q"] = normal_q
        q["all_normal_q"] = all_normal_q
        q["capital_q"] = capital_q
        q["feasibility"] = f
        q["skin_value_share"] = skin_share
        q["loc"] = locations[int(p["start_location_id"])]
        feasible.append(q)

    print(
        f"HVC feasible={len(feasible):,}; "
        f"capital-containing={sum(bool(x['capital_q']) for x in feasible):,}"
    )
    if not feasible:
        write_empty("No feasible high-value deep candidates.")
        return

    normal_tids = {int(tid) for p in feasible for tid in p["normal_q"]}
    live_buys, failed_buy, live_at_buy = fetch_live_jita_books(normal_tids, "buy")
    live_sells, failed_sell, live_at_sell = fetch_live_jita_books(normal_tids, "sell")

    capital_pairs = {
        (int(p["loc"].get("region_id") or 0), int(tid))
        for p in feasible for tid in p["capital_q"]
        if int(p["loc"].get("region_id") or 0) > 0
    }
    region_buys, failed_region_buy = fetch_region_buys(capital_pairs)

    history_candidates = sorted(
        feasible,
        key=lambda p: p.get("snapshot_list_profit", -1e30),
        reverse=True,
    )[:HISTORY_CANDIDATES]
    history_ids = {int(tid) for p in history_candidates for tid in p["normal_q"]}
    history, failed_history = fetch_market_history(history_ids)
    history_candidate_ids = {int(p["contract_id"]) for p in history_candidates}

    rows = []
    for p in feasible:
        cid = int(p["contract_id"])
        price = float(p["contract_price"])
        loc = p["loc"]
        region_id = int(loc.get("region_id") or 0)
        normal_q, capital_q = p["normal_q"], p["capital_q"]

        normal_cash = cash_quote(normal_q, live_buys)
        normal_stress = stress_cash(normal_q, live_buys)

        cap_books = {int(tid): region_buys.get((region_id, int(tid)), []) for tid in capital_q}
        cap_cash = cash_quote(capital_q, cap_books)
        cap_stress = stress_cash(capital_q, cap_books)

        normal_m3 = volume(p["all_normal_q"], types)
        haul = haul_reserve(normal_m3, loc) if p["all_normal_q"] else 0.0

        cap_cash_net = cap_cash["net_after_tax"] * (1.0 - CAPITAL_LOCAL_RISK_RATE)
        cap_stress_net = cap_stress["net_after_tax"] * (1.0 - CAPITAL_LOCAL_RISK_RATE)

        cash_value = normal_cash["net_after_tax"] + cap_cash_net - haul
        cash_profit = cash_value - price
        cash_roi = cash_profit / (price + haul) if price + haul > 0 else 0.0
        cash_stress_profit = normal_stress["net_after_tax"] + cap_stress_net - haul - price

        cash_valid = (
            not bool(set(normal_q).intersection(failed_buy))
            and not any((region_id, int(tid)) in failed_region_buy for tid in capital_q)
            and (not normal_q or normal_cash["filled_units"] > 0)
            and (not capital_q or cap_cash["filled_units"] > 0)
        )

        list_complete = False
        list_value = list_profit = list_roi = list_stress_profit = 0.0
        fill_days = 0.0
        if cid in history_candidate_ids and not bool(set(normal_q).intersection(failed_sell | failed_history)):
            if normal_q:
                qlist = conservative_listing_bundle(
                    normal_q,
                    live_sells,
                    history,
                    haircut=LIST_HAIRCUT,
                    participation=LIST_PARTICIPATION,
                )
            else:
                qlist = {"complete": True, "gross": 0.0, "estimated_fill_days": 0.0}
            if qlist["complete"]:
                fill_days = float(qlist["estimated_fill_days"])
                normal_list_net = listing_net(float(qlist["gross"]))
                list_value = normal_list_net + cap_cash_net - haul
                list_profit = list_value - price
                list_roi = list_profit / (price + haul) if price + haul > 0 else 0.0
                shocked = float(qlist["gross"]) * (1.0 - STRESS_PRICE_SHOCK)
                list_stress_profit = listing_net(shocked) + cap_stress_net - haul - price
                list_complete = fill_days <= LIST_MAX_FILL_DAYS

        split_best_value = max(cash_value, list_value if list_complete else 0.0)
        split_best_profit = split_best_value - price

        cash_proves = (
            cash_valid and cash_profit >= MIN_PROFIT and cash_roi >= MIN_ROI
            and cash_stress_profit > 0
        )
        list_proves = (
            list_complete and list_profit >= MIN_PROFIT and list_roi >= MIN_ROI
            and list_stress_profit > 0
        )
        proofs = []
        if cash_proves:
            proofs.append(("CASH_FLOOR", cash_profit, cash_roi, cash_stress_profit, cash_value))
        if list_proves:
            proofs.append(("CONSERVATIVE_7D", list_profit, list_roi, list_stress_profit, list_value))
        proofs.sort(key=lambda x: (x[3], x[1]), reverse=True)

        blocked = ""
        if p["skin_value_share"] >= SKIN_MAJOR_SHARE:
            blocked = "skin_major_share"
        elif p["capital_bucket"] != "ACTIONABLE":
            blocked = "capital_bucket_not_actionable"
        elif not proofs:
            blocked = "no_conservative_profit_proof"

        if proofs:
            basis, net_profit, net_roi, stress_profit, chosen_value = proofs[0]
        elif list_complete:
            basis, net_profit, net_roi, stress_profit, chosen_value = (
                "CONSERVATIVE_7D", list_profit, list_roi, list_stress_profit, list_value
            )
        else:
            basis, net_profit, net_roi, stress_profit, chosen_value = (
                "CASH_FLOOR", cash_profit, cash_roi, cash_stress_profit, cash_value
            )

        if proofs and not blocked:
            status = "SAFE"
        elif p["capital_bucket"] == "RESEARCH":
            status = "RESEARCH"
        else:
            status = "WATCH"

        score = opportunity_score(
            net_profit,
            max(0.0, net_roi),
            max(0.0, net_profit / max(1.0, normal_m3)),
            75.0 if basis == "CASH_FLOOR" else 65.0,
            stress_profit,
            loc.get("risk_rank", 5),
            max(0.5, fill_days * 24 if basis == "CONSERVATIVE_7D" else 1.0),
            0.0,
            "SAFE" if status == "SAFE" else "CHANGED",
        )

        rows.append({
            "engine_version": "High Value Contract Engine V1",
            "contract_id": cid,
            "contract_price": price,
            "capital_bucket": p["capital_bucket"],
            "execution_status": status,
            "proof_basis": basis,
            "blocked_reason": blocked,
            "score_grade": score_grade(score),
            "opportunity_score": score,
            "net_profit": net_profit,
            "net_roi": net_roi,
            "stress_net_profit": stress_profit,
            "chosen_estimated_value": chosen_value,
            "cash_floor_value": cash_value,
            "cash_floor_profit": cash_profit,
            "cash_floor_roi": cash_roi,
            "cash_floor_stress_profit": cash_stress_profit,
            "conservative_7d_value": list_value,
            "conservative_7d_profit": list_profit,
            "conservative_7d_roi": list_roi,
            "conservative_7d_stress_profit": list_stress_profit,
            "estimated_fill_days": fill_days,
            "split_best_value": split_best_value,
            "split_best_profit": split_best_profit,
            "jita_cash_coverage": normal_cash["coverage"],
            "capital_local_cash_coverage": cap_cash["coverage"],
            "has_capital_ship": bool(capital_q),
            "normal_item_type_count": len(p["all_normal_q"]),
            "live_valued_normal_type_count": len(normal_q),
            "ignored_normal_type_count": max(0, len(p["all_normal_q"]) - len(normal_q)),
            "capital_item_type_count": len(capital_q),
            "skin_value_share": p["skin_value_share"],
            "excluded_rig_qty": sum(p["feasibility"].excluded_rigs.values()),
            "excluded_market_singleton_qty": sum(p["feasibility"].excluded_market_singletons.values()),
            "haul_reserve": haul,
            "capital_local_risk_reserve_rate": CAPITAL_LOCAL_RISK_RATE,
            "normal_items": items_text(normal_q, types),
            "capital_items": items_text(capital_q, types),
            "cash_top_items": top_cash_items(normal_cash, types),
            "contract_title": p.get("contract_title", ""),
            "date_issued": p.get("date_issued", ""),
            "date_expired": p.get("date_expired", ""),
            "contracts_snapshot_modified": c_modified,
            "market_snapshot_modified": m_modified,
            "live_revalidated_at": max(live_at_buy, live_at_sell),
            "friendly_alliance_id": own_aid,
            "friendly_alliance_name": own_name,
            "friendly_alliance_ticker": own_ticker,
            "eve_contract_url": f"https://eve-contract-opener.99617224.workers.dev/c/{cid}",
            **loc,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        rank = {"SAFE": 0, "WATCH": 1, "RESEARCH": 2}
        df["_rank"] = df["execution_status"].map(rank).fillna(9)
        df.sort_values(
            ["_rank", "opportunity_score", "stress_net_profit", "net_profit"],
            ascending=[True, False, False, False],
            inplace=True,
        )
        df.drop(columns=["_rank"], inplace=True)
    df.to_csv(ALL_RESULT, index=False)

    actionable = df[
        (df["capital_bucket"] == "ACTIONABLE")
        & (df["execution_status"] == "SAFE")
        & (pd.to_numeric(df["net_profit"], errors="coerce").fillna(0) >= MIN_PROFIT)
        & (pd.to_numeric(df["net_roi"], errors="coerce").fillna(0) >= MIN_ROI)
    ].copy() if not df.empty else pd.DataFrame()
    actionable.to_csv(ACTIONABLE_RESULT, index=False)

    watch = df[df["capital_bucket"].isin(["WATCH", "RESEARCH"])].copy() if not df.empty else pd.DataFrame()
    watch.to_csv(WATCH_RESULT, index=False)

    lines = [
        "# High Value Contract Engine V1",
        "",
        f"- Scope: pure multi-item contracts above {MIN_PRICE/1e9:.1f}B ISK.",
        f"- Actionable: <= {ACTIONABLE_CAPITAL/1e9:.1f}B; watch: <= {WATCH_MAX/1e9:.1f}B; higher contracts research-only.",
        f"- Auto-push proof: net profit >= {MIN_PROFIT/1e6:.0f}M, ROI >= {MIN_ROI:.0%}, stress profit > 0.",
        f"- 7-day conservative listing requires <= {LIST_MAX_FILL_DAYS:.0f} days and {LIST_HAIRCUT:.0%} price haircut.",
        f"- Capital hulls are not deleted: same-region public buy depth is valued separately with {CAPITAL_LOCAL_RISK_RATE:.0%} risk reserve.",
        f"- Coarse universe: {len(universe):,}; deep validated: {len(df):,}; actionable SAFE: {len(actionable):,}.",
        "",
    ]
    if not actionable.empty:
        lines += [
            "| # | Contract | Price | Proof | Net | ROI | Stress | Capital | Location |",
            "|---:|---:|---:|---|---:|---:|---:|---|---|",
        ]
        for i, r in enumerate(actionable.head(20).itertuples(index=False), 1):
            lines.append(
                f"| {i} | {int(r.contract_id)} | {r.contract_price/1e9:.2f}B | {r.proof_basis} | "
                f"{r.net_profit/1e6:.0f}M | {r.net_roi:.1%} | {r.stress_net_profit/1e6:.0f}M | "
                f"{'yes' if r.has_capital_ship else 'no'} | {r.system_name} |"
            )
    else:
        lines.append("No <=8B contract currently passes the conservative high-value proof.")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        f"HVC done: universe={len(universe)} deep={len(df)} "
        f"actionable_safe={len(actionable)} watch_research={len(watch)}"
    )
    if not actionable.empty:
        print(actionable[[
            "contract_id", "contract_price", "proof_basis", "net_profit",
            "net_roi", "stress_net_profit", "has_capital_ship", "system_name"
        ]].head(20).to_string(index=False))


if __name__ == "__main__":
    main()
