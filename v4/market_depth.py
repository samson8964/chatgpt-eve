"""Auditable market top-five distinct price LEVELS and station sell-type coverage.

"Five groups" means distinct quoted prices. Same-price orders form one
price level, not five separate samples; simple mean is unweighted by volume.
Top five asks ascend; top five Jita bids descend. All numbers are ISK/unit.
"""
from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable

STATIONS = {
    "4-H": 1053970513596,
    "C-J": 1049588174021,
    "O4T": 1040804972352,
}
JITA = 60003760
TOP_LEVELS = 5


def top_price_levels(orders: Iterable, *, buy: bool, limit: int = TOP_LEVELS) -> dict:
    if not 1 <= limit <= 20:
        raise ValueError("INVALID_TOP_PRICE_LEVELS")
    # Numeric price keys: a station's multiple same-price orders are ONE level.
    prices = set()
    for o in orders:
        if bool(o.buy) != buy or o.remaining <= 0:
            raise ValueError("WRONG_SIDE_OR_NONACTIVE_MARKET_ORDER")
        price = float(o.price)
        if not math.isfinite(price) or price <= 0:
            raise ValueError("INVALID_MARKET_PRICE")
        prices.add(price)
    chosen = sorted(prices, reverse=buy)[:limit]
    return {
        "group_count": len(chosen),
        "simple_mean_isk_per_unit": (sum(chosen) / len(chosen) if chosen else None),
        "group_prices_isk": chosen,
        "convention": ("HIGHEST_BUY_DISTINCT_PRICE_LEVELS" if buy
                       else "LOWEST_SELL_DISTINCT_PRICE_LEVELS"),
        "average": "UNWEIGHTED_ARITHMETIC_MEAN_OF_DISTINCT_PRICE_LEVELS",
    }


def station_sell_census(markets: dict, *, locations: dict = STATIONS,
                        jita: int = JITA, floor: float = 50_000_000) -> dict:
    """Cover ALL *active* source sell types, not only profitable survivors.

    This is a type/price census against Jita bids. Not a live trade check.
    Full order-depth/haul evaluation stays downstream behind the safe
    optimistic upper-bound gate, preventing high-cost O(types * orders)
    work for economically impossible products.
    """
    output = {}
    for name, location in locations.items():
        sell_types = set()
        buy_types = set()
        sell_count = buy_count = 0
        for (lid, typ, is_buy), book in markets.items():
            if lid != location:
                continue
            if is_buy:
                buy_types.add(int(typ))
                buy_count += len(book)
            else:
                sell_types.add(int(typ))
                sell_count += len(book)
        covered = crossed = eligible = 0
        no_jita = 0
        for typ in sell_types:
            asks = markets[(location, typ, False)]
            bids = markets.get((jita, typ, True), ())
            if not bids:
                no_jita += 1
                continue
            covered += 1
            best_ask = min(o.price for o in asks)
            best_bid = max(o.price for o in bids)
            if best_ask < best_bid:
                crossed += 1
                optimistic = (best_bid - best_ask) * sum(o.remaining for o in asks)
                if optimistic >= floor:
                    eligible += 1
        output[name] = {
            "location_id": location,
            "active_sell_orders": sell_count,
            "active_sell_type_ids": len(sell_types),
            "all_active_type_ids": len(sell_types | buy_types),
            "all_active_orders": sell_count + buy_count,
            "active_buy_orders": buy_count,
            "active_buy_type_ids": len(buy_types),
            "sell_types_with_jita_buy": covered,
            "sell_types_without_jita_buy": no_jita,
            "sell_types_best_price_crossed": crossed,
            "sell_types_optimistic_gate_passed": eligible,
            "coverage": "ALL_VALID_ACTIVE_SOURCE_SELL_TYPES_TESTED_AGAINST_JITA_BUY_EXISTENCE_AND_BEST_PRICE",
            "full_order_depth_evaluated_only_after_optimistic_profit_gate": True,
        }
    return output
