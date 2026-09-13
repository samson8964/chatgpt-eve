from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

from contract_deal_scanner import SALES_TAX_RATE
from opportunity_engine_v2 import JITA_44, THE_FORGE, drop_best_price_level, fetch_live_jita_buy_books, liquidity_score_from_fill_days, safe_float, safe_int, walk_book
from scanner_source import fetch_many_ref, manufacturing_recipe, material_units_for_job

ESI = "https://esi.evetech.net/latest"
UA = "chatgpt-eve-bpc-v2/1.0"
LIVE_POOL = int(os.getenv("BPC_V2_LIVE_POOL", "50"))
LIVE_WORKERS = int(os.getenv("BPC_V2_LIVE_WORKERS", "16"))
MIN_PROFIT = float(os.getenv("BPC_V2_MIN_NET_PROFIT", "20000000"))
MIN_ROI = float(os.getenv("BPC_V2_MIN_NET_ROI", "0.10"))
MAX_SLIPPAGE = float(os.getenv("BPC_V2_MAX_SLIPPAGE", "0.05"))
MAX_CHANGE = float(os.getenv("BPC_V2_MAX_CHANGE", "0.15"))
PARTICIPATION = float(os.getenv("BPC_V2_LIQUIDITY_PARTICIPATION", "0.35"))
MFG_SOURCE = Path("results/latest/ranked_opportunities.csv")
MFG_V2 = Path("results/latest/ranked_opportunities_v2.csv")
VALUE_SOURCE = Path("results/latest/bpc_value_opportunities.csv")
VALUE_V2 = Path("results/latest/bpc_value_opportunities_v2.csv")


def _get(url, params=None, timeout=30):
    last = None
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=timeout)
            if r.status_code in (420, 429, 500, 502, 503, 504) and attempt < 2:
                continue
            r.raise_for_status()
            return r.json(), r.headers
        except Exception as exc:
            last = exc
    raise RuntimeError(str(last))


def contract_items(contract_id: int):
    data, _ = _get(f"{ESI}/contracts/public/items/{int(contract_id)}/", {"datasource": "tranquility", "page": 1})
    return data or []


def _fetch_book(type_id: int, side: str):
    rows = []
    page = 1
    while True:
        data, headers = _get(
            f"{ESI}/markets/{THE_FORGE}/orders/",
            {"datasource": "tranquility", "order_type": side, "type_id": int(type_id), "page": page},
        )
        for r in data or []:
            if safe_int(r.get("location_id"), 0) != JITA_44:
                continue
            is_buy = bool(r.get("is_buy_order"))
            if (side == "buy") != is_buy:
                continue
            vol = safe_int(r.get("volume_remain"), 0)
            price = safe_float(r.get("price"), 0)
            if vol > 0 and price > 0:
                rows.append({"price": price, "vol": vol, "min": max(1, safe_int(r.get("min_volume"), 1)), "order_id": safe_int(r.get("order_id"), 0)})
        pages = max(1, safe_int(headers.get("X-Pages"), 1))
        if page >= pages:
            break
        page += 1
    rows.sort(key=lambda x: (x["price"], x["order_id"]), reverse=(side == "buy"))
    return int(type_id), rows


def fetch_books(type_ids, side: str):
    ids = sorted({int(x) for x in type_ids if int(x) > 0})
    out, failed = {}, set()
    if not ids:
        return out, failed
    with ThreadPoolExecutor(max_workers=min(LIVE_WORKERS, len(ids))) as ex:
        futs = {ex.submit(_fetch_book, tid, side): tid for tid in ids}
        for fut in as_completed(futs):
            tid = futs[fut]
            try:
                rt, book = fut.result()
                out[rt] = book
            except Exception:
                failed.add(tid)
    return out, failed


def build_job(items):
    bpcs = []
    for item in items:
        if not bool(item.get("is_included", True)):
            return None, "buyer_must_supply_items"
        if not bool(item.get("is_blueprint_copy", False)):
            return None, "non_bpc_item_in_contract"
        tid = safe_int(item.get("type_id"), 0)
        runs = safe_int(item.get("runs"), 0)
        copies = max(1, safe_int(item.get("quantity"), 1))
        me = safe_int(item.get("material_efficiency"), 0)
        te = safe_int(item.get("time_efficiency"), 0)
        if tid <= 0 or runs <= 0:
            return None, "invalid_bpc"
        bpcs.append((tid, runs, copies, me, te))
    if not bpcs:
        return None, "no_bpc"

    bp_objs = fetch_many_ref("blueprints", [x[0] for x in bpcs])
    mats, products = {}, {}
    blueprint_rows = []
    for tid, runs, copies, me, te in bpcs:
        recipe = manufacturing_recipe(bp_objs.get(tid))
        if not recipe:
            return None, f"no_manufacturing_recipe:{tid}"
        base_mats, base_products = recipe
        for mtid, base_qty in base_mats.items():
            per_copy = material_units_for_job(int(base_qty), int(runs), int(me))
            mats[int(mtid)] = mats.get(int(mtid), 0) + per_copy * copies
        for ptid, base_qty in base_products.items():
            products[int(ptid)] = products.get(int(ptid), 0) + int(base_qty) * runs * copies
        blueprint_rows.append({"type_id": tid, "runs": runs, "copies": copies, "me": me, "te": te})
    if len(products) != 1:
        return None, "multi_product_job"
    return {"materials": mats, "products": products, "blueprints": blueprint_rows}, ""


def quote_bundle(itemq, books, side: str):
    total = 0.0
    stress_total = 0.0
    complete = True
    stress_complete = True
    max_slippage = 0.0
    rows = []
    for tid, qty in itemq.items():
        book = books.get(int(tid), [])
        fill = walk_book(book, int(qty))
        stress = walk_book(drop_best_price_level(book), int(qty))
        total += fill.value
        stress_total += stress.value
        complete = complete and fill.complete
        stress_complete = stress_complete and stress.complete
        max_slippage = max(max_slippage, fill.slippage_pct)
        rows.append({"type_id": int(tid), "quantity": int(qty), "complete": fill.complete, "best": fill.best_price, "vwap": fill.avg_price, "worst": fill.worst_price, "slippage": fill.slippage_pct})
    return {"value": total, "stress_value": stress_total, "complete": complete and bool(itemq), "stress_complete": stress_complete and bool(itemq), "max_slippage": max_slippage, "rows": rows, "side": side}


def history_metrics(product_type_id: int, qty: int):
    try:
        arr, _ = _get(f"{ESI}/markets/{THE_FORGE}/history/", {"datasource": "tranquility", "type_id": int(product_type_id)})
    except Exception:
        return {"days": 0, "avg_daily": 0.0, "fill_rate": 0.0, "fill_days": math.inf, "liquidity_score": 0.0, "liquidity_label": "unknown"}
    rows = list(arr or [])[-30:]
    vols = [max(0.0, safe_float(x.get("volume"), 0.0)) for x in rows]
    avg = sum(vols) / len(vols) if vols else 0.0
    executable_daily = avg * PARTICIPATION
    fill_days = float(qty) / executable_daily if executable_daily > 0 else math.inf
    required_market_volume = float(qty) / PARTICIPATION if PARTICIPATION > 0 else math.inf
    enough = sum(1 for v in vols if v >= required_market_volume)
    fill_rate = enough / len(vols) if vols else 0.0
    score, label = liquidity_score_from_fill_days(fill_days, bool(vols))
    return {"days": len(vols), "avg_daily": avg, "fill_rate": fill_rate, "fill_days": fill_days, "liquidity_score": score, "liquidity_label": label}


def classify(complete, live_profit, live_roi, stress_profit, change_pct, max_slippage, data_failed=False):
    if data_failed or not complete or live_profit < MIN_PROFIT or live_roi < MIN_ROI:
        return "DANGER"
    if stress_profit <= 0 or abs(change_pct) > MAX_CHANGE or max_slippage > MAX_SLIPPAGE:
        return "CHANGED"
    return "SAFE"


def score(live_profit, live_roi, liquidity, stress_profit, max_slippage, status, capital_days):
    p = min(30.0, max(0.0, live_profit) / 100_000_000 * 30.0)
    r = min(25.0, max(0.0, live_roi) / 0.30 * 25.0)
    l = min(20.0, max(0.0, liquidity) / 100.0 * 20.0)
    s = min(15.0, max(0.0, stress_profit) / max(live_profit, 1.0) * 15.0)
    slip = max(0.0, 10.0 * (1.0 - min(max_slippage, 0.10) / 0.10))
    time_penalty = min(12.0, max(0.0, capital_days - 1.0) * 1.5)
    state_penalty = 0.0 if status == "SAFE" else 20.0 if status == "CHANGED" else 50.0
    return round(max(0.0, min(100.0, p + r + l + s + slip - time_penalty - state_penalty)), 1)


def grade(v2_score, status):
    if status != "SAFE":
        return "C" if status == "CHANGED" else "D"
    if v2_score >= 85:
        return "S"
    if v2_score >= 70:
        return "A"
    if v2_score >= 55:
        return "B"
    return "C"


def enrich_manufacturing(path=MFG_SOURCE, out=MFG_V2):
    if not Path(path).exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    if df.empty:
        df.to_csv(out, index=False)
        return df

    df = df.sort_values([c for c in ["opportunity_score", "net_profit"] if c in df.columns], ascending=False).head(LIVE_POOL).copy()
    jobs = {}
    job_errors = {}
    for idx, r in df.iterrows():
        cid = safe_int(r.get("contract_id"), 0)
        try:
            job, err = build_job(contract_items(cid))
        except Exception as exc:
            job, err = None, f"contract_not_live:{type(exc).__name__}"
        if job:
            jobs[idx] = job
        else:
            job_errors[idx] = err

    material_ids = {tid for j in jobs.values() for tid in j["materials"]}
    product_ids = {tid for j in jobs.values() for tid in j["products"]}
    sell_books, failed_sells = fetch_books(material_ids, "sell")
    buy_books, failed_buys, verified_at = fetch_live_jita_buy_books(product_ids, workers=LIVE_WORKERS)

    rows = []
    for idx, r in df.iterrows():
        rr = r.to_dict()
        snapshot_profit = safe_float(r.get("net_profit"), 0.0)
        rr["v2_verified_at"] = verified_at
        rr["v2_snapshot_net_profit"] = snapshot_profit
        if idx not in jobs:
            rr.update({"v2_status": "DANGER", "v2_grade": "D", "v2_score": 0.0, "v2_warning": job_errors.get(idx, "job_unavailable")})
            rows.append(rr)
            continue

        job = jobs[idx]
        materials = job["materials"]
        products = job["products"]
        product_tid, output_qty = next(iter(products.items()))
        material_q = quote_bundle(materials, sell_books, "buy_materials")
        product_q = quote_bundle(products, buy_books, "sell_products")
        data_failed = bool(set(materials) & failed_sells) or product_tid in failed_buys
        fixed = safe_float(r.get("contract_price"), 0) + safe_float(r.get("manufacturing_job_cost"), 0) + safe_float(r.get("configured_haul_cost"), 0)
        live_revenue = product_q["value"]
        live_tax = live_revenue * SALES_TAX_RATE
        live_profit = live_revenue - live_tax - material_q["value"] - fixed
        invested = safe_float(r.get("contract_price"), 0) + material_q["value"] + safe_float(r.get("manufacturing_job_cost"), 0) + safe_float(r.get("configured_haul_cost"), 0)
        live_roi = live_profit / invested if invested > 0 else 0.0
        stress_revenue = product_q["stress_value"]
        stress_tax = stress_revenue * SALES_TAX_RATE
        stress_profit = stress_revenue - stress_tax - material_q["stress_value"] - fixed
        change_pct = (live_profit - snapshot_profit) / abs(snapshot_profit) if snapshot_profit else (0.0 if live_profit == 0 else 1.0)
        max_slip = max(material_q["max_slippage"], product_q["max_slippage"])
        complete = material_q["complete"] and product_q["complete"]
        hist = history_metrics(product_tid, output_qty)
        capital_days = safe_float(r.get("serial_job_hours"), 0) / 24.0 + (hist["fill_days"] if math.isfinite(hist["fill_days"]) else 30.0)
        status = classify(complete, live_profit, live_roi, stress_profit, change_pct, max_slip, data_failed)
        v2_score = score(live_profit, live_roi, hist["liquidity_score"], stress_profit, max_slip, status, capital_days)
        rr.update({
            "v2_status": status,
            "v2_grade": grade(v2_score, status),
            "v2_score": v2_score,
            "v2_warning": "" if status == "SAFE" else "live_revalidation_changed_or_failed",
            "v2_live_material_cost": material_q["value"],
            "v2_live_gross_revenue": live_revenue,
            "v2_live_sales_tax": live_tax,
            "v2_live_net_profit": live_profit,
            "v2_live_net_roi": live_roi,
            "v2_stress_net_profit": stress_profit,
            "v2_profit_change_pct": change_pct,
            "v2_material_max_slippage": material_q["max_slippage"],
            "v2_product_slippage": product_q["max_slippage"],
            "v2_product_best_buy": product_q["rows"][0]["best"] if product_q["rows"] else 0.0,
            "v2_product_vwap": product_q["rows"][0]["vwap"] if product_q["rows"] else 0.0,
            "v2_product_worst_buy": product_q["rows"][0]["worst"] if product_q["rows"] else 0.0,
            "v2_orderbook_complete": complete,
            "v2_avg_daily_volume_30d": hist["avg_daily"],
            "v2_est_fill_days": hist["fill_days"] if math.isfinite(hist["fill_days"]) else 999.0,
            "v2_historical_fill_rate": hist["fill_rate"],
            "v2_liquidity_score": hist["liquidity_score"],
            "v2_liquidity_label": hist["liquidity_label"],
            "v2_capital_lock_days": capital_days,
            "v2_return_per_capital_day": live_roi / capital_days if capital_days > 0 else 0.0,
            "v2_material_type_count": len(materials),
            "v2_live_product_type_id": product_tid,
            "v2_live_output_qty": output_qty,
        })
        rows.append(rr)

    out_df = pd.DataFrame(rows)
    if not out_df.empty:
        rank = {"SAFE": 0, "CHANGED": 1, "DANGER": 2}
        out_df["_v2_rank"] = out_df["v2_status"].map(rank).fillna(3)
        out_df.sort_values(["_v2_rank", "v2_score", "v2_live_net_profit"], ascending=[True, False, False], inplace=True)
        out_df.drop(columns=["_v2_rank"], inplace=True)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out, index=False)
    return out_df


def enrich_intrinsic(path=VALUE_SOURCE, out=VALUE_V2):
    if not Path(path).exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    rows = []
    for _, r in df.head(max(LIVE_POOL * 2, 100)).iterrows():
        rr = r.to_dict()
        cid = safe_int(r.get("contract_id"), 0)
        live = True
        try:
            contract_items(cid)
        except Exception:
            live = False
        n = max(0, safe_int(r.get("bpc_market_sample_count"), 0))
        median = safe_float(r.get("bpc_market_median_per_run"), 0)
        p25 = safe_float(r.get("bpc_market_p25_per_run"), 0)
        p75 = safe_float(r.get("bpc_market_p75_per_run"), 0)
        dispersion = (p75 - p25) / median if median > 0 and p75 >= p25 else 1.0
        sample_conf = min(1.0, n / 10.0)
        dispersion_conf = max(0.15, 1.0 - min(1.0, max(0.0, dispersion)))
        exact_bonus = 0.10 if "_ME" in str(r.get("bpc_market_basis", "")) else 0.0
        confidence = min(1.0, 0.65 * sample_conf + 0.25 * dispersion_conf + exact_bonus)
        discount = -safe_float(r.get("bpc_discount_vs_median"), 0.0)
        surplus = safe_float(r.get("bpc_intrinsic_value_surplus"), 0.0)
        risk_rank = safe_int(r.get("risk_rank"), 5)
        strong = live and n >= 5 and discount >= 0.20 and surplus >= 20_000_000 and confidence >= 0.55 and risk_rank <= 2
        value_score = min(100.0, max(0.0, confidence * 45 + min(35.0, discount / 0.60 * 35.0) + min(20.0, surplus / 200_000_000 * 20.0) - max(0, risk_rank - 1) * 5))
        rr.update({"v2_value_status": "VALUE_SIGNAL" if strong else "WATCH", "v2_value_score": round(value_score, 1), "v2_value_confidence": round(confidence, 4), "v2_value_dispersion_iqr": dispersion, "v2_contract_live": live, "v2_value_note": "Comparable public contract asks are a valuation signal, not guaranteed liquidation profit."})
        rows.append(rr)
    out_df = pd.DataFrame(rows)
    if not out_df.empty:
        out_df.sort_values(["v2_value_status", "v2_value_score", "bpc_intrinsic_value_surplus"], ascending=[True, False, False], inplace=True)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out, index=False)
    return out_df


def main():
    mfg = enrich_manufacturing()
    value = enrich_intrinsic()
    safe_count = int((mfg.get("v2_status", pd.Series(dtype=str)) == "SAFE").sum()) if not mfg.empty else 0
    value_count = int((value.get("v2_value_status", pd.Series(dtype=str)) == "VALUE_SIGNAL").sum()) if not value.empty else 0
    print(f"BPC V2 complete: manufacturing rows={len(mfg)} SAFE={safe_count}; intrinsic rows={len(value)} strong_value_signals={value_count}")


if __name__ == "__main__":
    main()
