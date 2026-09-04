from __future__ import annotations

import math
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from scanner_source import (
    PUBLIC_CONTRACTS_INDEX,
    MARKET_ORDERS_INDEX,
    DATA,
    LATEST,
    latest_file,
    download,
    load_contracts,
    load_market_orders,
    prepare_jita_books,
    fill_book,
    truthy_series,
    type_volume,
    esi_get,
)
from contract_deal_scanner import (
    SALES_TAX_RATE,
    BROKER_FEE_RATE,
    RELIST_RESERVE_RATE,
    current_friendly_alliances,
    sovereignty_owners,
    load_structures,
    resolve_location,
    haul_reserve,
)

THE_FORGE_REGION_ID = 10000002
RESULT = LATEST / "multi_item_contract_deals.csv"
ALL_RESULT = LATEST / "multi_item_contract_all.csv"

MIN_TYPES = int(os.getenv("MULTI_MIN_TYPES", "2"))
MIN_CONTRACT_PRICE = float(os.getenv("MULTI_MIN_CONTRACT_PRICE", "1000000"))
MIN_DISCOUNT = float(os.getenv("MULTI_MIN_DISCOUNT", "0.30"))
MIN_VALUE_GAP = float(os.getenv("MULTI_MIN_VALUE_GAP", "30000000"))
MIN_VALUE_COVERAGE = float(os.getenv("MULTI_MIN_VALUE_COVERAGE", "0.90"))
MIN_A_BUY_COVERAGE = float(os.getenv("MULTI_MIN_A_BUY_COVERAGE", "0.90"))
MIN_HOURS_TO_EXPIRE = float(os.getenv("MULTI_MIN_HOURS_TO_EXPIRE", "1"))
HISTORY_WORKERS = int(os.getenv("MULTI_HISTORY_WORKERS", "16"))
TOP_OUTPUT = int(os.getenv("MULTI_TOP", "250"))


def safe_num(v, default=0.0):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def aggregate_items(items: pd.DataFrame):
    out = defaultdict(int)
    for r in items.itertuples(index=False):
        try:
            tid = int(r.type_id)
            qty = int(r.quantity)
        except Exception:
            continue
        if tid > 0 and qty > 0:
            out[tid] += qty
    return dict(out)


def market_price_fallbacks():
    try:
        rows = esi_get("/markets/prices/", {"datasource": "tranquility"}, refresh=True)
    except Exception as e:
        print(f"multi market-price fallback failed: {e}")
        return {}
    out = {}
    for r in rows or []:
        try:
            tid = int(r["type_id"])
            p = safe_num(r.get("average_price"), 0.0) or safe_num(r.get("adjusted_price"), 0.0)
            if p > 0:
                out[tid] = p
        except Exception:
            pass
    return out


def raw_value(itemq, buy_books, sell_books, fallback_prices):
    buy_gross = 0.0
    sell_gross = 0.0
    buy_filled_units = 0
    total_units = 0
    priced_sell_value = 0.0
    fallback_missing_value = 0.0
    unknown_types = 0
    type_rows = []

    for tid, qty in itemq.items():
        total_units += qty
        bf = fill_book(buy_books.get(int(tid), []), qty)
        sf = fill_book(sell_books.get(int(tid), []), qty)
        fallback = safe_num(fallback_prices.get(int(tid)), 0.0)

        buy_gross += safe_num(bf.value, 0.0)
        buy_filled_units += int(bf.filled or 0)
        sell_gross += safe_num(sf.value, 0.0)
        priced_sell_value += safe_num(sf.value, 0.0)

        missing = max(0, qty - int(sf.filled or 0))
        if missing > 0:
            if fallback > 0:
                fallback_missing_value += fallback * missing
            else:
                unknown_types += 1

        type_rows.append({
            "type_id": int(tid),
            "quantity": int(qty),
            "buy_value": safe_num(bf.value, 0.0),
            "buy_filled": int(bf.filled or 0),
            "sell_value": safe_num(sf.value, 0.0),
            "sell_filled": int(sf.filled or 0),
            "fallback_price": fallback,
        })

    denom = priced_sell_value + fallback_missing_value
    coverage = priced_sell_value / denom if denom > 0 else 0.0
    if unknown_types:
        type_ratio = max(0.0, (len(itemq) - unknown_types) / max(1, len(itemq)))
        coverage = min(coverage, type_ratio)

    return {
        "jita_buy_gross": buy_gross,
        "jita_sell_gross_raw": sell_gross,
        "buy_unit_coverage": buy_filled_units / total_units if total_units else 0.0,
        "value_coverage": coverage,
        "unknown_price_types": unknown_types,
        "type_rows": type_rows,
    }


def history_for_type(type_id):
    try:
        rows = esi_get(
            f"/markets/{THE_FORGE_REGION_ID}/history/",
            {"datasource": "tranquility", "type_id": int(type_id)},
            cache_key=f"multi_history_{type_id}",
        )
    except Exception:
        return {"avg_daily_volume": 0.0, "traded_days": 0}
    if not rows:
        return {"avg_daily_volume": 0.0, "traded_days": 0}

    df = pd.DataFrame(rows)
    if df.empty or "date" not in df.columns or "volume" not in df.columns:
        return {"avg_daily_volume": 0.0, "traded_days": 0}
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=30)
    df = df[df["date"] >= cutoff].copy()
    if df.empty:
        return {"avg_daily_volume": 0.0, "traded_days": 0}
    return {
        "avg_daily_volume": float(df["volume"].sum()) / 30.0,
        "traded_days": int((df["volume"] > 0).sum()),
    }


def liquidity_factor(qty, history):
    avg = safe_num(history.get("avg_daily_volume"), 0.0)
    if avg <= 0:
        return 0.50
    days_to_sell = qty / avg
    if days_to_sell <= 3:
        return 1.00
    if days_to_sell <= 10:
        return 0.90
    if days_to_sell <= 30:
        return 0.70
    return 0.50


def major_type_ids(type_rows):
    rows = sorted(type_rows, key=lambda x: safe_num(x.get("sell_value"), 0.0), reverse=True)
    total = sum(safe_num(r.get("sell_value"), 0.0) for r in rows)
    if total <= 0:
        return {int(r["type_id"]) for r in rows[:10]}
    out = set()
    acc = 0.0
    for r in rows:
        v = safe_num(r.get("sell_value"), 0.0)
        out.add(int(r["type_id"]))
        acc += v
        if len(out) >= 10 or acc / total >= 0.95:
            break
    return out


def type_name(type_id, cache):
    tid = int(type_id)
    if tid in cache:
        return cache[tid]
    try:
        row = esi_get(f"/universe/types/{tid}/", {"datasource": "tranquility"}, cache_key=f"type_{tid}")
        name = str(row.get("name") or tid)
    except Exception:
        name = str(tid)
    cache[tid] = name
    return name


def main():
    print("multi 1) latest contract + Jita datasets")
    c_url, _ = latest_file(PUBLIC_CONTRACTS_INDEX)
    m_url, _ = latest_file(MARKET_ORDERS_INDEX)
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

    c = contracts[(contracts["type"] == "item_exchange") & (contracts["price"] >= MIN_CONTRACT_PRICE)].copy()
    c = c[c["start_location_id"].notna()].copy()
    now = pd.Timestamp.now(tz="UTC")
    if "date_expired" in c.columns:
        exp = pd.to_datetime(c["date_expired"], utc=True, errors="coerce")
        c = c[exp.isna() | (exp > now + pd.Timedelta(hours=MIN_HOURS_TO_EXPIRE))].copy()

    valid_ids = set(c["contract_id"].dropna().astype(int))
    ii = items[items["contract_id"].isin(valid_ids)].copy()
    ii["contract_id"] = pd.to_numeric(ii["contract_id"], errors="coerce").astype("Int64")
    ii["_included"] = truthy_series(ii["is_included"])
    ii["_bpc"] = truthy_series(ii["is_blueprint_copy"])
    ii["quantity"] = pd.to_numeric(ii["quantity"], errors="coerce").fillna(0).astype(int)
    ii["type_id"] = pd.to_numeric(ii["type_id"], errors="coerce").fillna(0).astype(int)

    requested_ids = set(ii.loc[~ii["_included"], "contract_id"].dropna().astype(int))
    bpc_ids = set(ii.loc[ii["_included"] & ii["_bpc"], "contract_id"].dropna().astype(int))
    usable_ids = valid_ids - requested_ids - bpc_ids
    inc = ii[ii["contract_id"].isin(usable_ids) & ii["_included"] & (ii["quantity"] > 0) & (ii["type_id"] > 0)].copy()

    grouped = {int(cid): aggregate_items(g) for cid, g in inc.groupby("contract_id", sort=False)}
    grouped = {cid: q for cid, q in grouped.items() if len(q) >= MIN_TYPES}
    c = c[c["contract_id"].isin(grouped.keys())].copy()
    c_by_id = c.set_index("contract_id", drop=False)
    print(f"multi contracts with >= {MIN_TYPES} item types: {len(grouped)}")

    print("multi 2) Jita books + broad valuation")
    orders = load_market_orders(m_path)
    sell_books, buy_books = prepare_jita_books(orders)
    del orders
    fallback_prices = market_price_fallbacks()

    prelim = []
    for cid, itemq in grouped.items():
        r = raw_value(itemq, buy_books, sell_books, fallback_prices)
        price = safe_num(c_by_id.loc[cid, "price"], 0.0)
        raw_value_est = safe_num(r["jita_sell_gross_raw"], 0.0)
        raw_gap = raw_value_est - price
        raw_discount = raw_gap / raw_value_est if raw_value_est > 0 else -1.0
        if r["value_coverage"] < MIN_VALUE_COVERAGE:
            continue
        if raw_gap < MIN_VALUE_GAP or raw_discount < MIN_DISCOUNT:
            continue
        prelim.append({
            "contract_id": cid,
            "contract_price": price,
            "start_location_id": int(c_by_id.loc[cid, "start_location_id"]),
            "item_type_count": len(itemq),
            "itemq": itemq,
            **r,
            "raw_gap": raw_gap,
            "raw_discount": raw_discount,
        })
    prelim.sort(key=lambda x: x["raw_gap"], reverse=True)
    print(f"multi broad value candidates={len(prelim)}")

    print("multi 3) resolve reachable locations")
    friendly_ids, _, _, _ = current_friendly_alliances()
    sov_map = sovereignty_owners()
    structure_ids = {r["start_location_id"] for r in prelim if r["start_location_id"] >= 1_000_000_000_000}
    structures = load_structures(structure_ids)
    reachable = []
    for r in prelim:
        loc = resolve_location(r["start_location_id"], structures, friendly_ids, sov_map)
        if not loc:
            continue
        if int(loc.get("system_id", 0) or 0) <= 0:
            continue
        if int(loc.get("shortest_jumps_to_jita", -1) or -1) < 0:
            continue
        rr = dict(r)
        rr["location"] = loc
        reachable.append(rr)
    print(f"multi reachable candidates={len(reachable)}")

    print("multi 4) liquidity history for major value contributors")
    wanted_types = set()
    for r in reachable:
        wanted_types |= major_type_ids(r["type_rows"])
    histories = {}
    if wanted_types:
        with ThreadPoolExecutor(max_workers=min(HISTORY_WORKERS, len(wanted_types))) as ex:
            futs = {ex.submit(history_for_type, tid): tid for tid in wanted_types}
            for fut in as_completed(futs):
                tid = futs[fut]
                try:
                    histories[tid] = fut.result()
                except Exception:
                    histories[tid] = {"avg_daily_volume": 0.0, "traded_days": 0}
    print(f"multi history types={len(histories)}")

    print("multi 5) final A/B economics")
    final_rows = []
    all_rows = []
    name_cache = {}
    for r in reachable:
        itemq = r["itemq"]
        major = major_type_ids(r["type_rows"])
        adjusted_rows = []
        adjusted_market_gross = 0.0
        for tr in r["type_rows"]:
            tid = int(tr["type_id"])
            qty = int(tr["quantity"])
            if tid in major:
                hist = histories.get(tid, {"avg_daily_volume": 0.0, "traded_days": 0})
                factor = liquidity_factor(qty, hist)
                avg_daily = safe_num(hist.get("avg_daily_volume"), 0.0)
            else:
                factor = 0.90
                avg_daily = 0.0
            adjusted_value = safe_num(tr.get("sell_value"), 0.0) * factor
            adjusted_market_gross += adjusted_value
            adjusted_rows.append({**tr, "liquidity_factor": factor, "avg_daily_volume": avg_daily, "adjusted_value": adjusted_value})

        loc = r["location"]
        total_m3 = 0.0
        for tid, qty in itemq.items():
            try:
                total_m3 += max(0.0, safe_num(type_volume(int(tid)), 0.0)) * qty
            except Exception:
                pass
        haul = haul_reserve(total_m3, loc)
        price = r["contract_price"]

        a_gross = safe_num(r["jita_buy_gross"], 0.0)
        a_tax = a_gross * SALES_TAX_RATE
        a_net_value = a_gross - a_tax - haul
        a_gap = a_net_value - price
        a_discount = a_gap / a_net_value if a_net_value > 0 else -1.0
        a_roi = a_gap / price if price > 0 else -1.0
        a_ok = (
            safe_num(r["buy_unit_coverage"], 0.0) >= MIN_A_BUY_COVERAGE
            and a_gap >= MIN_VALUE_GAP
            and a_discount >= MIN_DISCOUNT
        )

        b_broker = adjusted_market_gross * BROKER_FEE_RATE
        b_tax = adjusted_market_gross * SALES_TAX_RATE
        b_relist = adjusted_market_gross * RELIST_RESERVE_RATE
        b_net_value = adjusted_market_gross - b_broker - b_tax - b_relist - haul
        b_gap = b_net_value - price
        b_discount = b_gap / b_net_value if b_net_value > 0 else -1.0
        b_roi = b_gap / price if price > 0 else -1.0
        b_ok = b_gap >= MIN_VALUE_GAP and b_discount >= MIN_DISCOUNT

        deal_class = "A 多件即时兑现" if a_ok else ("B 多件价值低估" if b_ok else "")
        chosen_value = a_net_value if a_ok else b_net_value
        chosen_gap = a_gap if a_ok else b_gap
        chosen_discount = a_discount if a_ok else b_discount
        chosen_roi = a_roi if a_ok else b_roi

        adjusted_sorted = sorted(adjusted_rows, key=lambda x: safe_num(x.get("adjusted_value"), 0.0), reverse=True)
        total_adj = sum(safe_num(x.get("adjusted_value"), 0.0) for x in adjusted_sorted)
        top1_share = safe_num(adjusted_sorted[0].get("adjusted_value"), 0.0) / total_adj if adjusted_sorted and total_adj > 0 else 0.0
        top3_share = sum(safe_num(x.get("adjusted_value"), 0.0) for x in adjusted_sorted[:3]) / total_adj if total_adj > 0 else 0.0

        base_row = {
            "contract_id": int(r["contract_id"]),
            "deal_class": deal_class,
            "contract_price": price,
            "item_type_count": int(r["item_type_count"]),
            "value_coverage": safe_num(r["value_coverage"], 0.0),
            "unknown_price_types": int(r["unknown_price_types"]),
            "buy_unit_coverage": safe_num(r["buy_unit_coverage"], 0.0),
            "jita_buy_gross": a_gross,
            "instant_liquidation_net_value": a_net_value,
            "instant_value_gap": a_gap,
            "instant_discount": a_discount,
            "instant_roi": a_roi,
            "jita_sell_gross_raw": safe_num(r["jita_sell_gross_raw"], 0.0),
            "liquidity_adjusted_market_gross": adjusted_market_gross,
            "market_net_value": b_net_value,
            "market_value_gap": b_gap,
            "market_discount": b_discount,
            "market_roi": b_roi,
            "chosen_estimated_value": chosen_value,
            "chosen_value_gap": chosen_gap,
            "chosen_discount": chosen_discount,
            "chosen_roi": chosen_roi,
            "sales_tax_if_instant": a_tax,
            "list_broker_fee": b_broker,
            "list_sales_tax": b_tax,
            "list_relist_reserve": b_relist,
            "haul_reserve": haul,
            "total_m3": total_m3,
            "top1_value_share": top1_share,
            "top3_value_share": top3_share,
            **loc,
        }
        all_rows.append(base_row)
        if not deal_class:
            continue

        item_bits = []
        for tr in adjusted_sorted:
            name = type_name(tr["type_id"], name_cache)
            item_bits.append(
                f"{name} x{int(tr['quantity'])}≈{safe_num(tr['adjusted_value'],0.0):.0f} "
                f"(liq×{safe_num(tr['liquidity_factor'],0.0):.2f})"
            )
        base_row["item_breakdown"] = " | ".join(item_bits)
        base_row["top_value_items"] = " | ".join(item_bits[:6])
        final_rows.append(base_row)

    all_df = pd.DataFrame(all_rows)
    if not all_df.empty:
        all_df.sort_values(["market_value_gap", "instant_value_gap"], ascending=False, inplace=True)
    ALL_RESULT.parent.mkdir(parents=True, exist_ok=True)
    all_df.to_csv(ALL_RESULT, index=False)

    out = pd.DataFrame(final_rows)
    if not out.empty:
        out.sort_values(["chosen_value_gap", "chosen_roi"], ascending=False, inplace=True)
        out = out.head(TOP_OUTPUT).copy()
    out.to_csv(RESULT, index=False)
    print(
        f"multi done: final={len(out)} output={RESULT}; "
        f"threshold discount>={MIN_DISCOUNT:.0%} gap>={MIN_VALUE_GAP/1e6:.0f}M coverage>={MIN_VALUE_COVERAGE:.0%}"
    )


if __name__ == "__main__":
    main()
