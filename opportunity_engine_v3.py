from __future__ import annotations

import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Iterable

import requests

from opportunity_engine_v2 import (
    ESI,
    JITA_44,
    THE_FORGE,
    safe_float,
    safe_int,
    walk_book,
)

UA = "chatgpt-eve-opportunity-engine-v3/1.0"
LIVE_WORKERS = int(os.getenv("V3_LIVE_WORKERS", "14"))
HTTP_TIMEOUT = int(os.getenv("V3_HTTP_TIMEOUT", "30"))

# V3 is deliberately additive: V2 remains the high-confidence full-liquidation
# engine, while V3 discovers opportunities V2 structurally misses.
CASH_FLOOR_MIN_PROFIT = float(os.getenv("V3_CASH_FLOOR_MIN_PROFIT", "30000000"))
CASH_FLOOR_MIN_ROI = float(os.getenv("V3_CASH_FLOOR_MIN_ROI", "0.10"))
BARTER_MIN_PROFIT = float(os.getenv("V3_BARTER_MIN_PROFIT", "30000000"))
BARTER_MIN_ROI = float(os.getenv("V3_BARTER_MIN_ROI", "0.10"))
LIST_MIN_PROFIT = float(os.getenv("V3_LIST_MIN_PROFIT", "50000000"))
LIST_MIN_ROI = float(os.getenv("V3_LIST_MIN_ROI", "0.20"))
LIST_MAX_FILL_DAYS = float(os.getenv("V3_LIST_MAX_FILL_DAYS", "14"))
LIST_PARTICIPATION = float(os.getenv("V3_LIST_PARTICIPATION", "0.20"))
LIST_PRICE_HAIRCUT = float(os.getenv("V3_LIST_PRICE_HAIRCUT", "0.05"))
SAFE_CHANGE_PCT = float(os.getenv("V3_SAFE_CHANGE_PCT", "0.15"))


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "t", "yes", "y"}


def _get_json(url: str, params: dict | None = None, tries: int = 3):
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


def _fetch_jita_book(type_id: int, side: str):
    rows = []
    page = 1
    try:
        while True:
            payload, headers = _get_json(
                f"{ESI}/markets/{THE_FORGE}/orders/",
                {
                    "datasource": "tranquility",
                    "order_type": side,
                    "type_id": int(type_id),
                    "page": page,
                },
            )
            for row in payload or []:
                if safe_int(row.get("location_id"), 0) != JITA_44:
                    continue
                is_buy = _truthy(row.get("is_buy_order", False))
                if (side == "buy") != is_buy:
                    continue
                vol = safe_int(row.get("volume_remain"), 0)
                price = safe_float(row.get("price"), 0.0)
                if vol <= 0 or price <= 0:
                    continue
                rows.append(
                    {
                        "price": price,
                        "vol": vol,
                        "min": max(1, safe_int(row.get("min_volume"), 1)),
                        "order_id": safe_int(row.get("order_id"), 0),
                    }
                )
            pages = max(1, safe_int(headers.get("X-Pages"), 1))
            if page >= pages:
                break
            page += 1
        rows.sort(key=lambda x: (x["price"], x.get("order_id", 0)), reverse=(side == "buy"))
        return int(type_id), rows, None
    except Exception as exc:
        return int(type_id), [], str(exc)


def fetch_live_jita_books(type_ids: Iterable[int], side: str, workers: int | None = None):
    ids = sorted({safe_int(x, 0) for x in type_ids if safe_int(x, 0) > 0})
    if not ids:
        return {}, set(), datetime.now(timezone.utc).isoformat()
    out, failed = {}, set()
    max_workers = min(max(1, workers or LIVE_WORKERS), len(ids))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_fetch_jita_book, tid, side): tid for tid in ids}
        for fut in as_completed(futs):
            tid = futs[fut]
            try:
                rt, book, err = fut.result()
            except Exception:
                failed.add(tid)
                continue
            out[rt] = book
            if err:
                failed.add(rt)
    return out, failed, datetime.now(timezone.utc).isoformat()


def partial_liquidation(itemq: dict[int, int], buy_books: dict[int, list[dict]], sales_tax_rate: float):
    """Value only units that can be sold now; leftovers are explicitly worth zero.

    This is the core CASH_FLOOR idea. An incomplete book is not a failure: the
    executable part is cash and the unsold remainder receives no value at all.
    """
    gross = 0.0
    requested = 0
    filled = 0
    matched_itemq: dict[int, int] = {}
    rows = []
    for tid, raw_qty in itemq.items():
        qty = max(0, safe_int(raw_qty, 0))
        if qty <= 0:
            continue
        fill = walk_book(buy_books.get(int(tid), []), qty)
        requested += qty
        filled += fill.filled
        gross += fill.value
        if fill.filled > 0:
            matched_itemq[int(tid)] = fill.filled
        rows.append(
            {
                "type_id": int(tid),
                "quantity": qty,
                "filled": fill.filled,
                "unvalued": max(0, qty - fill.filled),
                "gross": fill.value,
                "best_price": fill.best_price,
                "vwap": fill.avg_price,
                "worst_price": fill.worst_price,
                "slippage_pct": fill.slippage_pct,
            }
        )
    tax = gross * max(0.0, sales_tax_rate)
    return {
        "gross": gross,
        "sales_tax": tax,
        "net_after_tax": gross - tax,
        "requested_units": requested,
        "filled_units": filled,
        "coverage": filled / requested if requested else 0.0,
        "matched_itemq": matched_itemq,
        "rows": rows,
    }


def procurement_cost(itemq: dict[int, int], sell_books: dict[int, list[dict]]):
    """Cost to acquire required barter inputs. Unlike cash floor this must be complete."""
    total = 0.0
    complete = True
    rows = []
    for tid, raw_qty in itemq.items():
        qty = max(0, safe_int(raw_qty, 0))
        if qty <= 0:
            continue
        fill = walk_book(sell_books.get(int(tid), []), qty)
        total += fill.value
        complete = complete and fill.complete
        rows.append(
            {
                "type_id": int(tid),
                "quantity": qty,
                "complete": fill.complete,
                "cost": fill.value,
                "best_price": fill.best_price,
                "vwap": fill.avg_price,
                "worst_price": fill.worst_price,
                "slippage_pct": fill.slippage_pct,
            }
        )
    return {"complete": complete and bool(itemq), "cost": total, "rows": rows}


def _fetch_history(type_id: int):
    try:
        payload, _ = _get_json(
            f"{ESI}/markets/{THE_FORGE}/history/",
            {"datasource": "tranquility", "type_id": int(type_id)},
        )
        rows = sorted(payload or [], key=lambda x: str(x.get("date", "")))[-30:]
        if not rows:
            return int(type_id), {}, None
        last7 = rows[-7:]
        def weighted_average(group):
            volume = sum(max(0.0, safe_float(x.get("volume"), 0.0)) for x in group)
            if volume <= 0:
                return 0.0
            return sum(
                safe_float(x.get("average"), 0.0) * max(0.0, safe_float(x.get("volume"), 0.0))
                for x in group
            ) / volume
        vols = [max(0.0, safe_float(x.get("volume"), 0.0)) for x in rows]
        vols7 = [max(0.0, safe_float(x.get("volume"), 0.0)) for x in last7]
        return int(type_id), {
            "days": len(rows),
            "vwap_7d": weighted_average(last7),
            "vwap_30d": weighted_average(rows),
            "avg_daily_volume_7d": sum(vols7) / len(vols7) if vols7 else 0.0,
            "avg_daily_volume_30d": sum(vols) / len(vols) if vols else 0.0,
        }, None
    except Exception as exc:
        return int(type_id), {}, str(exc)


def fetch_market_history(type_ids: Iterable[int], workers: int | None = None):
    ids = sorted({safe_int(x, 0) for x in type_ids if safe_int(x, 0) > 0})
    if not ids:
        return {}, set()
    out, failed = {}, set()
    max_workers = min(max(1, workers or LIVE_WORKERS), len(ids))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_fetch_history, tid): tid for tid in ids}
        for fut in as_completed(futs):
            tid = futs[fut]
            try:
                rt, data, err = fut.result()
            except Exception:
                failed.add(tid)
                continue
            if data:
                out[rt] = data
            if err:
                failed.add(rt)
    return out, failed


def conservative_listing_bundle(
    itemq: dict[int, int],
    sell_books: dict[int, list[dict]],
    history: dict[int, dict],
    haircut: float | None = None,
    participation: float | None = None,
):
    """Conservative sell-order valuation for a bundle.

    Each unit is valued at the minimum of current best ask, 7d VWAP and 30d VWAP,
    then haircutted. Every type must have current asks and historical turnover.
    The worst fill-days across the bundle is reported.
    """
    hc = max(0.0, min(0.50, LIST_PRICE_HAIRCUT if haircut is None else haircut))
    part = max(0.01, min(1.0, LIST_PARTICIPATION if participation is None else participation))
    gross = 0.0
    worst_days = 0.0
    complete = True
    rows = []
    for tid, raw_qty in itemq.items():
        qty = max(0, safe_int(raw_qty, 0))
        if qty <= 0:
            continue
        book = sell_books.get(int(tid), [])
        h = history.get(int(tid)) or {}
        best_ask = safe_float(book[0].get("price"), 0.0) if book else 0.0
        v7 = safe_float(h.get("vwap_7d"), 0.0)
        v30 = safe_float(h.get("vwap_30d"), 0.0)
        avg_daily = safe_float(h.get("avg_daily_volume_7d"), 0.0) or safe_float(h.get("avg_daily_volume_30d"), 0.0)
        refs = [x for x in (best_ask, v7, v30) if x > 0]
        if len(refs) < 2 or avg_daily <= 0:
            complete = False
            rows.append({"type_id": int(tid), "quantity": qty, "known": False})
            continue
        unit_price = min(refs) * (1.0 - hc)
        fill_days = qty / max(avg_daily * part, 1e-9)
        worst_days = max(worst_days, fill_days)
        value = unit_price * qty
        gross += value
        rows.append(
            {
                "type_id": int(tid),
                "quantity": qty,
                "known": True,
                "best_ask": best_ask,
                "vwap_7d": v7,
                "vwap_30d": v30,
                "conservative_unit_price": unit_price,
                "estimated_fill_days": fill_days,
                "gross": value,
            }
        )
    return {
        "complete": complete and bool(itemq),
        "gross": gross,
        "estimated_fill_days": worst_days,
        "rows": rows,
    }


def material_change(snapshot_value: float, live_value: float):
    base = safe_float(snapshot_value, 0.0)
    live = safe_float(live_value, 0.0)
    if base <= 0:
        return 0.0 if live <= 0 else 1.0
    return (live - base) / base


def v3_status(
    profit: float,
    roi: float,
    stress_profit: float,
    min_profit: float,
    min_roi: float,
    change_pct: float = 0.0,
    fatal: bool = False,
):
    if fatal or profit < min_profit or roi < min_roi:
        return "DANGER"
    if stress_profit <= 0 or abs(change_pct) > SAFE_CHANGE_PCT:
        return "CHANGED"
    return "SAFE"


def diverse_candidates(
    rows: list[dict],
    total_limit: int,
    per_metric: int,
    metrics: tuple[str, ...] = ("snapshot_profit", "snapshot_roi"),
    newest_key: str = "date_issued",
    newest_count: int = 40,
):
    """Union several rankings instead of allowing one stale profit ranking to dominate."""
    if total_limit <= 0 or not rows:
        return []
    selected: dict[int, dict] = {}
    for metric in metrics:
        ranked = sorted(rows, key=lambda r: safe_float(r.get(metric), -math.inf), reverse=True)
        for row in ranked[: max(0, per_metric)]:
            selected[safe_int(row.get("contract_id"), 0)] = row
    newest = sorted(rows, key=lambda r: str(r.get(newest_key, "")), reverse=True)
    for row in newest[: max(0, newest_count)]:
        selected[safe_int(row.get("contract_id"), 0)] = row

    # Fill remaining capacity by the best available absolute profit while preserving
    # the union above. This keeps behavior deterministic and bounded.
    ranked_all = sorted(
        rows,
        key=lambda r: (
            safe_float(r.get("snapshot_profit"), -math.inf),
            safe_float(r.get("snapshot_roi"), -math.inf),
        ),
        reverse=True,
    )
    for row in ranked_all:
        if len(selected) >= total_limit:
            break
        selected.setdefault(safe_int(row.get("contract_id"), 0), row)
    out = list(selected.values())
    out.sort(
        key=lambda r: (
            safe_float(r.get("snapshot_profit"), -math.inf),
            safe_float(r.get("snapshot_roi"), -math.inf),
        ),
        reverse=True,
    )
    return out[:total_limit]
