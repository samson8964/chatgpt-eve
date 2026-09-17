from __future__ import annotations

import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Iterable

import requests

from opportunity_engine_v2 import ESI, JITA_44, THE_FORGE, drop_best_price_level, safe_float, safe_int, walk_book

UA = "chatgpt-eve-opportunity-engine-v3/1.0"
HTTP_TIMEOUT = int(os.getenv("V3_HTTP_TIMEOUT", "30"))
LIVE_WORKERS = int(os.getenv("V3_LIVE_WORKERS", "12"))
HISTORY_WORKERS = int(os.getenv("V3_HISTORY_WORKERS", "10"))
SELL_PARTICIPATION = float(os.getenv("V3_SELL_LIQUIDITY_PARTICIPATION", "0.20"))
SELL_PRICE_HAIRCUT = float(os.getenv("V3_SELL_PRICE_HAIRCUT", "0.97"))
SELL_STRESS_HAIRCUT = float(os.getenv("V3_SELL_STRESS_HAIRCUT", "0.10"))


def cash_floor_bundle(itemq: dict[int, int], buy_books: dict[int, list[dict]], sales_tax_rate: float) -> dict:
    """Value only units that can be sold to visible bids now; unfilled units are worth zero."""
    gross = stress_gross = 0.0
    requested_units = filled_units = stress_filled_units = 0
    rows = []
    for tid, raw_qty in itemq.items():
        qty = max(0, int(raw_qty))
        if qty <= 0:
            continue
        book = buy_books.get(int(tid), [])
        fill = walk_book(book, qty)
        stress = walk_book(drop_best_price_level(book), qty)
        gross += fill.value
        stress_gross += stress.value
        requested_units += qty
        filled_units += fill.filled
        stress_filled_units += stress.filled
        rows.append({
            "type_id": int(tid), "quantity": qty, "filled": fill.filled,
            "unsold": max(0, qty - fill.filled), "gross": fill.value,
            "best_price": fill.best_price, "vwap": fill.avg_price,
            "slippage_pct": fill.slippage_pct, "stress_filled": stress.filled,
            "stress_gross": stress.value,
        })
    tax = gross * max(0.0, sales_tax_rate)
    stress_tax = stress_gross * max(0.0, sales_tax_rate)
    return {
        "gross": gross, "sales_tax": tax, "net_after_tax": gross - tax,
        "stress_gross": stress_gross, "stress_sales_tax": stress_tax,
        "stress_net_after_tax": stress_gross - stress_tax,
        "requested_units": requested_units, "filled_units": filled_units,
        "stress_filled_units": stress_filled_units,
        "coverage": filled_units / requested_units if requested_units else 0.0,
        "stress_coverage": stress_filled_units / requested_units if requested_units else 0.0,
        "has_executable_value": gross > 0 and filled_units > 0, "rows": rows,
    }


def procure_bundle(itemq: dict[int, int], sell_books: dict[int, list[dict]]) -> dict:
    """Price goods that must be supplied to an exchange contract; requested goods must be complete."""
    if not itemq:
        return {"complete": True, "stress_complete": True, "cost": 0.0, "stress_cost": 0.0, "max_slippage_pct": 0.0, "rows": []}
    total = stress_total = 0.0
    complete = stress_complete = True
    max_slippage = 0.0
    rows = []
    for tid, raw_qty in itemq.items():
        qty = max(0, int(raw_qty))
        if qty <= 0:
            continue
        book = sell_books.get(int(tid), [])
        fill = walk_book(book, qty)
        stress = walk_book(drop_best_price_level(book), qty)
        total += fill.value
        stress_total += stress.value
        complete = complete and fill.complete
        stress_complete = stress_complete and stress.complete
        max_slippage = max(max_slippage, fill.slippage_pct)
        rows.append({
            "type_id": int(tid), "quantity": qty, "complete": fill.complete,
            "cost": fill.value, "best_price": fill.best_price, "vwap": fill.avg_price,
            "worst_price": fill.worst_price, "slippage_pct": fill.slippage_pct,
            "stress_complete": stress.complete, "stress_cost": stress.value,
        })
    return {"complete": complete, "stress_complete": stress_complete, "cost": total, "stress_cost": stress_total, "max_slippage_pct": max_slippage, "rows": rows}


def select_candidate_union(rows: list[dict], limit: int, profit_quota: int | None = None, roi_quota: int | None = None, recent_quota: int | None = None) -> list[dict]:
    """Diversify live validation across profit, ROI and newly issued contracts."""
    if not rows or limit <= 0:
        return []
    profit_quota = min(limit, profit_quota if profit_quota is not None else max(1, limit // 2))
    roi_quota = min(limit, roi_quota if roi_quota is not None else max(1, limit // 4))
    recent_quota = min(limit, recent_quota if recent_quota is not None else max(1, limit // 4))
    profit_key = lambda r: (safe_float(r.get("snapshot_profit"), -math.inf), safe_float(r.get("snapshot_roi"), -math.inf))
    roi_key = lambda r: (safe_float(r.get("snapshot_roi"), -math.inf), safe_float(r.get("snapshot_profit"), -math.inf))
    recent_key = lambda r: str(r.get("date_issued") or "")
    picked: dict[int, dict] = {}
    for group in (sorted(rows, key=profit_key, reverse=True)[:profit_quota], sorted(rows, key=roi_key, reverse=True)[:roi_quota], sorted(rows, key=recent_key, reverse=True)[:recent_quota]):
        for r in group:
            cid = safe_int(r.get("contract_id"), 0)
            if cid > 0:
                picked.setdefault(cid, r)
    if len(picked) < limit:
        for r in sorted(rows, key=profit_key, reverse=True):
            cid = safe_int(r.get("contract_id"), 0)
            if cid > 0:
                picked.setdefault(cid, r)
            if len(picked) >= limit:
                break
    return list(picked.values())[:limit]


def _get_json(url: str, params: dict | None = None, tries: int = 3):
    last = None
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=HTTP_TIMEOUT)
            if r.status_code in {420, 429, 500, 502, 503, 504} and attempt + 1 < tries:
                time.sleep(0.8 + attempt)
                continue
            r.raise_for_status()
            return r.json(), r.headers
        except Exception as exc:
            last = exc
            if attempt + 1 < tries:
                time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"ESI request failed: {url}: {last}")


def _fetch_live_jita_book(type_id: int, side: str):
    rows = []
    page = 1
    try:
        while True:
            payload, headers = _get_json(f"{ESI}/markets/{THE_FORGE}/orders/", {"datasource": "tranquility", "order_type": side, "type_id": int(type_id), "page": page})
            for row in payload or []:
                if safe_int(row.get("location_id"), 0) != JITA_44:
                    continue
                is_buy = bool(row.get("is_buy_order"))
                if (side == "buy") != is_buy:
                    continue
                vol = safe_int(row.get("volume_remain"), 0)
                price = safe_float(row.get("price"), 0.0)
                if vol <= 0 or price <= 0:
                    continue
                rows.append({"price": price, "vol": vol, "min": max(1, safe_int(row.get("min_volume"), 1)), "order_id": safe_int(row.get("order_id"), 0)})
            pages = max(1, safe_int(headers.get("X-Pages"), 1))
            if page >= pages:
                break
            page += 1
        rows.sort(key=lambda x: (x["price"], x.get("order_id", 0)), reverse=(side == "buy"))
        return int(type_id), rows, None
    except Exception as exc:
        return int(type_id), [], str(exc)


def fetch_live_jita_sell_books(type_ids: Iterable[int], workers: int | None = None):
    ids = sorted({int(x) for x in type_ids if safe_int(x, 0) > 0})
    if not ids:
        return {}, set(), datetime.now(timezone.utc).isoformat()
    out, failed = {}, set()
    max_workers = min(max(1, workers or LIVE_WORKERS), len(ids))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_fetch_live_jita_book, tid, "sell"): tid for tid in ids}
        for fut in as_completed(futs):
            tid = futs[fut]
            try:
                rt, book, err = fut.result()
            except Exception:
                failed.add(tid)
                continue
            if err:
                failed.add(rt)
            out[rt] = book
    return out, failed, datetime.now(timezone.utc).isoformat()


def _fetch_price_history_one(type_id: int):
    try:
        payload, _ = _get_json(f"{ESI}/markets/{THE_FORGE}/history/", {"datasource": "tranquility", "type_id": int(type_id)})
        rows = sorted(payload or [], key=lambda x: str(x.get("date", "")))[-30:]
        if not rows:
            return int(type_id), {}, None
        def metrics(window):
            subset = rows[-window:]
            volume = sum(max(0.0, safe_float(x.get("volume"), 0.0)) for x in subset)
            weighted = sum(max(0.0, safe_float(x.get("volume"), 0.0)) * max(0.0, safe_float(x.get("average"), 0.0)) for x in subset)
            return weighted / volume if volume > 0 else 0.0, volume / len(subset) if subset else 0.0
        v7, d7 = metrics(min(7, len(rows)))
        v30, d30 = metrics(len(rows))
        return int(type_id), {"days": len(rows), "vwap_7d": v7, "vwap_30d": v30, "avg_daily_volume_7d": d7, "avg_daily_volume_30d": d30}, None
    except Exception as exc:
        return int(type_id), {}, str(exc)


def fetch_jita_price_history(type_ids: Iterable[int], workers: int | None = None):
    ids = sorted({int(x) for x in type_ids if safe_int(x, 0) > 0})
    if not ids:
        return {}, set()
    out, failed = {}, set()
    max_workers = min(max(1, workers or HISTORY_WORKERS), len(ids))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_fetch_price_history_one, tid): tid for tid in ids}
        for fut in as_completed(futs):
            tid = futs[fut]
            try:
                rt, data, err = fut.result()
            except Exception:
                failed.add(tid)
                continue
            if err:
                failed.add(rt)
            if data:
                out[rt] = data
    return out, failed


def conservative_sell_bundle(itemq: dict[int, int], live_sell_books: dict[int, list[dict]], history_by_type: dict[int, dict], participation: float | None = None, price_haircut: float | None = None, min_history_days: int = 14) -> dict:
    """Conservative listing value: min(live ask, 7d VWAP, 30d VWAP) times a haircut."""
    part = max(0.01, min(1.0, participation if participation is not None else SELL_PARTICIPATION))
    haircut = max(0.50, min(1.0, price_haircut if price_haircut is not None else SELL_PRICE_HAIRCUT))
    gross = worst_days = 0.0
    complete = True
    rows = []
    for tid, raw_qty in itemq.items():
        qty = max(0, int(raw_qty))
        if qty <= 0:
            continue
        book = live_sell_books.get(int(tid), [])
        h = history_by_type.get(int(tid)) or {}
        best = safe_float(book[0].get("price"), 0.0) if book else 0.0
        v7 = safe_float(h.get("vwap_7d"), 0.0)
        v30 = safe_float(h.get("vwap_30d"), 0.0)
        days = safe_int(h.get("days"), 0)
        daily7 = safe_float(h.get("avg_daily_volume_7d"), 0.0)
        daily30 = safe_float(h.get("avg_daily_volume_30d"), 0.0)
        daily = daily7 if daily7 > 0 else daily30
        anchors = [x for x in (best, v7, v30) if x > 0]
        known = bool(book) and days >= min_history_days and len(anchors) >= 2 and daily > 0
        if not known:
            complete = False
            rows.append({"type_id": int(tid), "quantity": qty, "known": False})
            continue
        exit_price = min(anchors) * haircut
        fill_days = qty / (daily * part) if daily * part > 0 else math.inf
        worst_days = max(worst_days, fill_days)
        gross += exit_price * qty
        rows.append({"type_id": int(tid), "quantity": qty, "known": True, "live_best_sell": best, "vwap_7d": v7, "vwap_30d": v30, "exit_price": exit_price, "fill_days": fill_days, "avg_daily_volume": daily})
    stress_gross = gross * (1.0 - max(0.0, min(0.50, SELL_STRESS_HAIRCUT)))
    return {"complete": complete and bool(rows), "gross": gross, "stress_gross": stress_gross, "fill_days": worst_days, "rows": rows}
