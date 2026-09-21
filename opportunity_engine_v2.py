from __future__ import annotations

import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import requests

ESI = "https://esi.evetech.net/latest"
THE_FORGE = 10000002
JITA_44 = 60003760
UA = "chatgpt-eve-opportunity-engine-v2/1.0"

LIVE_WORKERS = int(os.getenv("V2_LIVE_WORKERS", "12"))
HISTORY_WORKERS = int(os.getenv("V2_HISTORY_WORKERS", "10"))
HTTP_TIMEOUT = int(os.getenv("V2_HTTP_TIMEOUT", "30"))
LIQUIDITY_PARTICIPATION = float(os.getenv("V2_LIQUIDITY_PARTICIPATION", "0.35"))
HAUL_CAPACITY_M3 = float(os.getenv("V2_HAUL_CAPACITY_M3", "60000"))
SECONDS_PER_JUMP = float(os.getenv("V2_SECONDS_PER_JUMP", "50"))
FIXED_MINUTES_PER_TRIP = float(os.getenv("V2_FIXED_MINUTES_PER_TRIP", "8"))
SAFE_PRICE_CHANGE_PCT = float(os.getenv("V2_SAFE_PRICE_CHANGE_PCT", "0.10"))

# Conservative high-sec exclusions. Name fallback below covers future/new groups.
HIGHSEC_RESTRICTED_GROUP_IDS = {30, 485, 547, 659, 883, 1538}
SMALL_SHIP_GROUP_IDS = {25, 324, 420, 831, 834, 893, 1527, 2016}
MEDIUM_SHIP_GROUP_IDS = {26, 28, 358, 419, 832, 833, 894, 906, 963, 1201, 1305, 1534, 2017, 2018}
LARGE_SHIP_GROUP_IDS = {27, 381, 485, 513, 547, 659, 883, 898, 900, 902, 941, 1538, 2019}


@dataclass
class BookFill:
    complete: bool
    value: float
    filled: int
    requested: int
    avg_price: float
    best_price: float
    worst_price: float
    total_depth: int
    slippage_pct: float
    levels_used: int


@dataclass
class TransportEstimate:
    trips: int
    route_jumps: int
    total_leg_jumps: int
    hours: float
    isk_per_hour: float


@dataclass
class ContractFeasibility:
    adjusted_itemq: dict[int, int]
    excluded_rigs: dict[int, int]
    excluded_market_singletons: dict[int, int]
    has_ship: bool
    has_highsec_restricted_ship: bool
    warnings: list[str]


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else default
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "t", "yes", "y"}


def _name(obj: dict | None) -> str:
    if not obj:
        return ""
    n = obj.get("name")
    if isinstance(n, str):
        return n
    if isinstance(n, dict):
        return str(n.get("en") or n.get("zh") or next(iter(n.values()), ""))
    return str(obj.get("name_en") or "")


def _group_id(type_obj: dict | None) -> int:
    if not type_obj:
        return 0
    return safe_int(type_obj.get("group_id", type_obj.get("groupID", 0)), 0)


def _category_id(type_obj: dict | None, group_obj: dict | None) -> int:
    for obj in (type_obj, group_obj):
        if not obj:
            continue
        for key in ("category_id", "categoryID"):
            if obj.get(key) is not None:
                return safe_int(obj.get(key), 0)
    return 0


def walk_book(book: list[dict], qty: int) -> BookFill:
    """Walk a pre-sorted order book and compute executable VWAP/slippage.

    The caller controls sort direction: bids should be descending, asks ascending.
    This is intentionally conservative around min-volume orders: an order is only
    consumed when the current fill chunk meets its minimum.
    """
    requested = max(0, int(qty))
    if requested <= 0:
        return BookFill(True, 0.0, 0, 0, 0.0, 0.0, 0.0, 0, 0.0, 0)

    total_depth = sum(max(0, safe_int(o.get("vol"), 0)) for o in book)
    left = requested
    value = 0.0
    filled = 0
    best = 0.0
    worst = 0.0
    levels = 0

    for order in book:
        if left <= 0:
            break
        vol = max(0, safe_int(order.get("vol"), 0))
        price = safe_float(order.get("price"), 0.0)
        min_volume = max(1, safe_int(order.get("min"), 1))
        if vol <= 0 or price <= 0:
            continue
        take = min(left, vol)
        if take < min_volume:
            continue
        if best <= 0:
            best = price
        worst = price
        value += price * take
        filled += take
        left -= take
        levels += 1

    avg = value / filled if filled else 0.0
    slippage = abs(avg - best) / best if best > 0 else 0.0
    return BookFill(
        complete=left == 0,
        value=value,
        filled=filled,
        requested=requested,
        avg_price=avg,
        best_price=best,
        worst_price=worst,
        total_depth=total_depth,
        slippage_pct=slippage,
        levels_used=levels,
    )


def drop_best_price_level(book: list[dict]) -> list[dict]:
    """Stress scenario: remove the entire best visible price level."""
    if not book:
        return []
    best = safe_float(book[0].get("price"), 0.0)
    if best <= 0:
        return list(book[1:])
    return [o for o in book if not math.isclose(safe_float(o.get("price"), 0.0), best, rel_tol=0.0, abs_tol=1e-9)]


def liquidate_bundle(
    itemq: dict[int, int],
    buy_books: dict[int, list[dict]],
    sales_tax_rate: float,
    value_factors: dict[int, float] | None = None,
) -> dict:
    """Liquidate a bundle into current buy-order depth, with a best-level stress test."""
    value_factors = value_factors or {}
    gross = 0.0
    stress_gross = 0.0
    requested_units = 0
    filled_units = 0
    complete = True
    stress_complete = True
    rows = []

    for tid, raw_qty in itemq.items():
        qty = max(0, int(raw_qty))
        if qty <= 0:
            continue
        factor = max(0.0, safe_float(value_factors.get(int(tid), 1.0), 1.0))
        book = buy_books.get(int(tid), [])
        fill = walk_book(book, qty)
        stress = walk_book(drop_best_price_level(book), qty)
        gross += fill.value * factor
        stress_gross += stress.value * factor
        requested_units += qty
        filled_units += fill.filled
        complete = complete and fill.complete
        stress_complete = stress_complete and stress.complete
        rows.append(
            {
                "type_id": int(tid),
                "quantity": qty,
                "value_factor": factor,
                "gross": fill.value * factor,
                "stress_gross": stress.value * factor,
                "complete": fill.complete,
                "stress_complete": stress.complete,
                "filled": fill.filled,
                "best_price": fill.best_price,
                "vwap": fill.avg_price,
                "worst_price": fill.worst_price,
                "slippage_pct": fill.slippage_pct,
                "book_depth": fill.total_depth,
                "levels_used": fill.levels_used,
            }
        )

    tax = gross * max(0.0, sales_tax_rate)
    stress_tax = stress_gross * max(0.0, sales_tax_rate)
    return {
        "complete": complete and requested_units > 0,
        "stress_complete": stress_complete and requested_units > 0,
        "gross": gross,
        "sales_tax": tax,
        "net_after_tax": gross - tax,
        "stress_gross": stress_gross,
        "stress_sales_tax": stress_tax,
        "stress_net_after_tax": stress_gross - stress_tax,
        "requested_units": requested_units,
        "filled_units": filled_units,
        "coverage": filled_units / requested_units if requested_units else 0.0,
        "rows": rows,
    }


def cross_book_arbitrage(
    asks: list[dict],
    bids: list[dict],
    sales_tax_rate: float,
    min_marginal_roi: float = 0.0,
    unit_volume_m3: float = 0.0,
    haul_cost_per_m3: float = 0.0,
) -> dict | None:
    """Match cheapest source asks to highest destination bids while marginal trade remains viable."""
    if not asks or not bids:
        return None

    ai = bi = 0
    ask_left = max(0, safe_int(asks[0].get("vol"), 0))
    bid_left = max(0, safe_int(bids[0].get("vol"), 0))
    qty = 0
    source_cost = 0.0
    gross = 0.0
    first_ask = safe_float(asks[0].get("price"), 0.0)
    first_bid = safe_float(bids[0].get("price"), 0.0)
    worst_ask = first_ask
    worst_bid = first_bid

    while ai < len(asks) and bi < len(bids):
        ask = asks[ai]
        bid = bids[bi]
        ask_price = safe_float(ask.get("price"), 0.0)
        bid_price = safe_float(bid.get("price"), 0.0)
        if ask_price <= 0 or bid_price <= 0:
            break
        unit_haul = max(0.0, unit_volume_m3) * max(0.0, haul_cost_per_m3)
        unit_net = bid_price * (1.0 - sales_tax_rate) - ask_price - unit_haul
        deployed = ask_price + unit_haul
        marginal_roi = unit_net / deployed if deployed > 0 else -1.0
        if unit_net <= 0 or marginal_roi < min_marginal_roi:
            break

        take = min(ask_left, bid_left)
        ask_min = max(1, safe_int(ask.get("min"), 1))
        bid_min = max(1, safe_int(bid.get("min"), 1))
        if take < ask_min:
            ai += 1
            if ai < len(asks):
                ask_left = max(0, safe_int(asks[ai].get("vol"), 0))
            continue
        if take < bid_min:
            bi += 1
            if bi < len(bids):
                bid_left = max(0, safe_int(bids[bi].get("vol"), 0))
            continue

        qty += take
        source_cost += ask_price * take
        gross += bid_price * take
        worst_ask = ask_price
        worst_bid = bid_price
        ask_left -= take
        bid_left -= take

        if ask_left <= 0:
            ai += 1
            if ai < len(asks):
                ask_left = max(0, safe_int(asks[ai].get("vol"), 0))
        if bid_left <= 0:
            bi += 1
            if bi < len(bids):
                bid_left = max(0, safe_int(bids[bi].get("vol"), 0))

    if qty <= 0 or source_cost <= 0:
        return None

    haul = max(0.0, unit_volume_m3) * qty * max(0.0, haul_cost_per_m3)
    tax = gross * max(0.0, sales_tax_rate)
    net_profit = gross - tax - source_cost - haul
    invested = source_cost + haul
    return {
        "quantity": qty,
        "source_cost": source_cost,
        "destination_gross": gross,
        "sales_tax": tax,
        "haul_cost": haul,
        "net_profit": net_profit,
        "net_roi": net_profit / invested if invested > 0 else 0.0,
        "source_best": first_ask,
        "source_worst": worst_ask,
        "destination_best": first_bid,
        "destination_worst": worst_bid,
        "source_slippage_pct": (worst_ask - first_ask) / first_ask if first_ask > 0 else 0.0,
        "destination_slippage_pct": (first_bid - worst_bid) / first_bid if first_bid > 0 else 0.0,
    }


def _esi_get_json(url: str, params: dict | None = None, tries: int = 3) -> tuple[Any, requests.structures.CaseInsensitiveDict]:
    last: Exception | None = None
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=HTTP_TIMEOUT)
            if r.status_code in {420, 429, 500, 502, 503, 504} and attempt + 1 < tries:
                time.sleep(1.0 + attempt)
                continue
            r.raise_for_status()
            return r.json(), r.headers
        except Exception as exc:
            last = exc
            if attempt + 1 < tries:
                time.sleep(0.7 * (attempt + 1))
    raise RuntimeError(f"ESI request failed: {url}: {last}")


def _fetch_live_jita_buy_book(type_id: int) -> tuple[int, list[dict], str | None]:
    rows: list[dict] = []
    page = 1
    try:
        while True:
            payload, headers = _esi_get_json(
                f"{ESI}/markets/{THE_FORGE}/orders/",
                {
                    "datasource": "tranquility",
                    "order_type": "buy",
                    "type_id": int(type_id),
                    "page": page,
                },
            )
            for row in payload or []:
                if safe_int(row.get("location_id"), 0) != JITA_44:
                    continue
                if not _truthy(row.get("is_buy_order", True)):
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
        rows.sort(key=lambda x: (x["price"], x.get("order_id", 0)), reverse=True)
        return int(type_id), rows, None
    except Exception as exc:
        return int(type_id), [], str(exc)


def fetch_live_jita_buy_books(type_ids: Iterable[int], workers: int | None = None) -> tuple[dict[int, list[dict]], set[int], str]:
    ids = sorted({int(x) for x in type_ids if safe_int(x, 0) > 0})
    if not ids:
        return {}, set(), datetime.now(timezone.utc).isoformat()
    out: dict[int, list[dict]] = {}
    failed: set[int] = set()
    max_workers = min(max(1, workers or LIVE_WORKERS), len(ids))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_fetch_live_jita_buy_book, tid): tid for tid in ids}
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


def _fetch_history_one(type_id: int) -> tuple[int, dict, str | None]:
    try:
        payload, _ = _esi_get_json(
            f"{ESI}/markets/{THE_FORGE}/history/",
            {"datasource": "tranquility", "type_id": int(type_id)},
        )
        rows = sorted(payload or [], key=lambda x: str(x.get("date", "")))[-30:]
        vols = [max(0, safe_int(x.get("volume"), 0)) for x in rows]
        last7 = vols[-7:]
        return int(type_id), {
            "days": len(vols),
            "volumes_30d": vols,
            "avg_daily_volume_7d": sum(last7) / len(last7) if last7 else 0.0,
            "avg_daily_volume_30d": sum(vols) / len(vols) if vols else 0.0,
        }, None
    except Exception as exc:
        return int(type_id), {}, str(exc)


def fetch_jita_history(type_ids: Iterable[int], workers: int | None = None) -> tuple[dict[int, dict], set[int]]:
    ids = sorted({int(x) for x in type_ids if safe_int(x, 0) > 0})
    if not ids:
        return {}, set()
    out: dict[int, dict] = {}
    failed: set[int] = set()
    max_workers = min(max(1, workers or HISTORY_WORKERS), len(ids))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_fetch_history_one, tid): tid for tid in ids}
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


def liquidity_score_from_fill_days(fill_days: float, history_available: bool = True) -> tuple[float, str]:
    if not history_available or fill_days <= 0 or not math.isfinite(fill_days):
        return 0.0, "unknown"
    if fill_days <= 1:
        return 100.0, "high"
    if fill_days <= 2:
        return 90.0, "high"
    if fill_days <= 3:
        return 80.0, "high"
    if fill_days <= 7:
        return 65.0, "medium"
    if fill_days <= 14:
        return 45.0, "medium"
    if fill_days <= 30:
        return 25.0, "low"
    return 10.0, "thin"


def bundle_liquidity(itemq: dict[int, int], history_by_type: dict[int, dict], participation: float | None = None) -> dict:
    part = max(0.01, min(1.0, participation if participation is not None else LIQUIDITY_PARTICIPATION))
    worst_days = 0.0
    min_fill_rate = 100.0
    known = 0
    rows = []
    for tid, raw_qty in itemq.items():
        qty = max(0, int(raw_qty))
        if qty <= 0:
            continue
        h = history_by_type.get(int(tid)) or {}
        avg7 = safe_float(h.get("avg_daily_volume_7d"), 0.0)
        avg30 = safe_float(h.get("avg_daily_volume_30d"), 0.0)
        daily = avg7 if avg7 > 0 else avg30
        vols = [safe_float(v, 0.0) for v in h.get("volumes_30d", [])]
        if daily <= 0 or not vols:
            rows.append({"type_id": int(tid), "quantity": qty, "fill_days": 0.0, "fill_rate_30d": 0.0, "known": False})
            continue
        known += 1
        executable_per_day = daily * part
        fill_days = qty / executable_per_day if executable_per_day > 0 else math.inf
        fill_rate = sum(1 for v in vols if v * part >= qty) / len(vols) * 100.0
        worst_days = max(worst_days, fill_days)
        min_fill_rate = min(min_fill_rate, fill_rate)
        rows.append(
            {
                "type_id": int(tid),
                "quantity": qty,
                "fill_days": fill_days,
                "fill_rate_30d": fill_rate,
                "avg_daily_volume_7d": avg7,
                "avg_daily_volume_30d": avg30,
                "known": True,
            }
        )

    score, label = liquidity_score_from_fill_days(worst_days, known > 0)
    if known > 0:
        score *= 0.5 + 0.5 * max(0.0, min(1.0, min_fill_rate / 100.0))
    else:
        min_fill_rate = 0.0
    return {
        "fill_time_days": worst_days,
        "liquidity_score": round(score, 1),
        "liquidity_label": label if known > 0 else "unknown",
        "historical_fill_rate_30d": round(min_fill_rate, 1) if known > 0 else 0.0,
        "history_known_types": known,
        "rows": rows,
    }


def _ship_size_class(type_obj: dict | None, group_obj: dict | None) -> int:
    gid = _group_id(type_obj)
    group_name = _name(group_obj).lower()
    if gid in SMALL_SHIP_GROUP_IDS or any(k in group_name for k in ("frigate", "destroyer", "shuttle", "corvette")):
        return 1
    if gid in MEDIUM_SHIP_GROUP_IDS or any(k in group_name for k in ("cruiser", "battlecruiser", "transport ship", "industrial ship", "mining barge", "exhumer")):
        return 2
    if gid in LARGE_SHIP_GROUP_IDS or any(k in group_name for k in ("battleship", "freighter", "carrier", "dreadnought", "capital industrial", "force auxiliary", "titan", "supercarrier")):
        return 3
    return 0


def _is_ship(type_obj: dict | None, group_obj: dict | None) -> bool:
    if _category_id(type_obj, group_obj) == 6:
        return True
    group_name = _name(group_obj).lower()
    return any(
        k in group_name
        for k in (
            "frigate", "destroyer", "cruiser", "battlecruiser", "battleship", "carrier", "dreadnought",
            "freighter", "industrial ship", "transport ship", "mining barge", "exhumer", "shuttle", "corvette",
            "supercarrier", "titan", "force auxiliary", "capital industrial", "strategic cruiser", "command ship",
        )
    )


def _is_highsec_restricted_ship(type_obj: dict | None, group_obj: dict | None) -> bool:
    gid = _group_id(type_obj)
    if gid in HIGHSEC_RESTRICTED_GROUP_IDS:
        return True
    g = _name(group_obj).strip().lower()
    return any(k in g for k in ("titan", "dreadnought", "carrier", "supercarrier", "force auxiliary", "capital industrial ship", "lancer dreadnought"))


def _is_rig(type_obj: dict | None, group_obj: dict | None) -> bool:
    g = _name(group_obj).lower()
    n = _name(type_obj).lower()
    return "rig" in g or n.startswith(("small ", "medium ", "large ", "capital ")) and " rig" in n


def _rig_size_class(type_obj: dict | None) -> int:
    n = _name(type_obj).strip().lower()
    if n.startswith("small "):
        return 1
    if n.startswith("medium "):
        return 2
    if n.startswith("large ") or n.startswith("capital "):
        return 3
    return 0


def aggregate_market_executable_items(
    item_rows: list[dict],
    type_objs: dict[int, dict] | None = None,
    group_objs: dict[int, dict] | None = None,
) -> tuple[dict[int, int], dict[int, int]]:
    """Aggregate only items that are safe to value against normal market orders.

    EVE contract rows marked singleton are item instances rather than ordinary
    stackable/repackaged market goods. They may be damaged/used crystals,
    damaged modules, fitted modules, etc. Those rows must not inherit the
    pristine type_id market price. Assembled ships are the deliberate exception:
    the hull can be repackaged after stripping fittings, and ship-specific rig
    handling is performed later by analyze_contract_items().

    Missing metadata is fail-closed for singleton rows: if we cannot prove that
    a singleton is a ship, it contributes zero market value.
    """
    type_objs = type_objs or {}
    group_objs = group_objs or {}
    aggregate: dict[int, int] = {}
    excluded: dict[int, int] = {}
    for row in item_rows:
        tid = safe_int(row.get("type_id"), 0)
        qty = safe_int(row.get("quantity"), 0)
        if tid <= 0 or qty <= 0:
            continue
        singleton = _truthy(row.get("is_singleton", row.get("singleton", False)))
        if singleton:
            tobj = type_objs.get(tid)
            gobj = group_objs.get(_group_id(tobj))
            if not _is_ship(tobj, gobj):
                excluded[tid] = excluded.get(tid, 0) + qty
                continue
        aggregate[tid] = aggregate.get(tid, 0) + qty
    return aggregate, excluded


def analyze_contract_items(item_rows: list[dict], type_objs: dict[int, dict], group_objs: dict[int, dict]) -> ContractFeasibility:
    """Apply conservative market-executability rules to contract contents.

    Non-ship singleton instances are excluded from normal market valuation.
    This prevents used/damaged frequency crystals and damaged/fitted modules
    from being valued as pristine market goods. Assembled ship hulls remain
    eligible, while likely fitted rigs are excluded separately.
    """
    ship_sizes: set[int] = set()
    restricted = False
    has_ship = False
    warnings: list[str] = []

    # First identify ships so the second pass can distinguish assembled hulls
    # and likely fitted rigs from other singleton item instances.
    for row in item_rows:
        tid = safe_int(row.get("type_id"), 0)
        qty = safe_int(row.get("quantity"), 0)
        if tid <= 0 or qty <= 0:
            continue
        tobj = type_objs.get(tid)
        gobj = group_objs.get(_group_id(tobj))
        if _is_ship(tobj, gobj):
            has_ship = True
            size = _ship_size_class(tobj, gobj)
            if size > 0:
                ship_sizes.add(size)
            if _is_highsec_restricted_ship(tobj, gobj):
                restricted = True

    aggregate: dict[int, int] = {}
    excluded_rigs: dict[int, int] = {}
    excluded_market_singletons: dict[int, int] = {}

    for row in item_rows:
        tid = safe_int(row.get("type_id"), 0)
        qty = safe_int(row.get("quantity"), 0)
        if tid <= 0 or qty <= 0:
            continue
        tobj = type_objs.get(tid)
        gobj = group_objs.get(_group_id(tobj))
        singleton = _truthy(row.get("is_singleton", row.get("singleton", False)))
        is_ship = _is_ship(tobj, gobj)

        # Keep the existing fitted-rig safeguard. It takes precedence over the
        # generic singleton rule so reporting can still identify rig exclusions.
        if has_ship and _is_rig(tobj, gobj):
            rig_size = _rig_size_class(tobj)
            if singleton or (rig_size > 0 and rig_size in ship_sizes):
                excluded_rigs[tid] = excluded_rigs.get(tid, 0) + qty
                continue

        # Market buy/sell orders are for normal marketable items, not singleton
        # instances. A non-ship singleton therefore gets zero executable value.
        if singleton and not is_ship:
            excluded_market_singletons[tid] = excluded_market_singletons.get(tid, 0) + qty
            continue

        aggregate[tid] = aggregate.get(tid, 0) + qty

    if excluded_rigs:
        warnings.append("likely_fitted_rigs_excluded")
    if excluded_market_singletons:
        warnings.append("market_ineligible_singletons_excluded")
    if restricted:
        warnings.append("highsec_restricted_ship")
    if has_ship:
        warnings.append("assembled_ship_contract")

    return ContractFeasibility(
        adjusted_itemq=aggregate,
        excluded_rigs=excluded_rigs,
        excluded_market_singletons=excluded_market_singletons,
        has_ship=has_ship,
        has_highsec_restricted_ship=restricted,
        warnings=warnings,
    )

def estimate_transport(total_m3: float, jumps: int, net_profit: float, capacity_m3: float | None = None) -> TransportEstimate:
    volume = max(0.0, safe_float(total_m3, 0.0))
    route_jumps = max(0, safe_int(jumps, 0))
    cap = max(1.0, safe_float(capacity_m3 if capacity_m3 is not None else HAUL_CAPACITY_M3, HAUL_CAPACITY_M3))
    trips = max(1, int(math.ceil(volume / cap))) if volume > 0 else 1
    total_leg_jumps = (2 * trips - 1) * route_jumps if route_jumps > 0 else 0
    hours = total_leg_jumps * max(1.0, SECONDS_PER_JUMP) / 3600.0 + trips * max(0.0, FIXED_MINUTES_PER_TRIP) / 60.0
    if hours <= 0:
        hours = max(0.05, trips * 0.05)
    return TransportEstimate(
        trips=trips,
        route_jumps=route_jumps,
        total_leg_jumps=total_leg_jumps,
        hours=hours,
        isk_per_hour=max(0.0, safe_float(net_profit, 0.0)) / hours,
    )


def snapshot_change_pct(snapshot_value: float, live_value: float) -> float:
    base = safe_float(snapshot_value, 0.0)
    live = safe_float(live_value, 0.0)
    if base <= 0:
        return 0.0 if live <= 0 else 1.0
    return (live - base) / base


def classify_execution_status(
    complete: bool,
    net_profit: float,
    roi: float,
    stress_profit: float,
    price_change_pct: float,
    fatal_warnings: Iterable[str] | None = None,
) -> str:
    fatal = {str(x) for x in (fatal_warnings or []) if x}
    if fatal or not complete or net_profit <= 0 or roi <= 0:
        return "DANGER"
    if stress_profit <= 0 or abs(price_change_pct) > SAFE_PRICE_CHANGE_PCT:
        return "CHANGED"
    return "SAFE"


def opportunity_score(
    net_profit: float,
    roi: float,
    profit_per_m3: float,
    liquidity_score: float,
    stress_profit: float,
    risk_rank: float,
    execution_hours: float,
    price_change_pct: float = 0.0,
    status: str = "SAFE",
) -> float:
    profit = max(0.0, safe_float(net_profit, 0.0))
    roi_v = max(0.0, safe_float(roi, 0.0))
    density = max(0.0, safe_float(profit_per_m3, 0.0))
    liq = max(0.0, min(100.0, safe_float(liquidity_score, 0.0)))
    stress = max(0.0, safe_float(stress_profit, 0.0))
    hours = max(0.05, safe_float(execution_hours, 0.05))
    risk = max(0.0, safe_float(risk_rank, 0.0))

    profit_component = min(30.0, math.log10(1.0 + profit / 1_000_000.0) / math.log10(1001.0) * 30.0)
    roi_component = min(25.0, roi_v / 0.30 * 25.0)
    liquidity_component = (liq / 100.0) * 15.0 if liq > 0 else 5.0
    stress_component = min(10.0, (stress / profit) * 10.0) if profit > 0 else 0.0
    density_component = min(10.0, math.log10(1.0 + density / 1_000.0) * 3.5)
    iskph = profit / hours
    speed_component = min(10.0, math.log10(1.0 + iskph / 1_000_000.0) / math.log10(501.0) * 10.0)

    score = profit_component + roi_component + liquidity_component + stress_component + density_component + speed_component
    score -= min(20.0, risk * 4.0)
    score -= min(12.0, abs(price_change_pct) * 40.0)
    if status == "CHANGED":
        score *= 0.80
    elif status == "DANGER":
        score *= 0.20
    return round(max(0.0, min(100.0, score)), 1)


def score_grade(score: float) -> str:
    s = safe_float(score, 0.0)
    if s >= 85:
        return "S"
    if s >= 70:
        return "A"
    if s >= 55:
        return "B"
    if s >= 40:
        return "C"
    return "D"


def dataclass_dict(value: Any) -> dict:
    return asdict(value)
