"""Depth-aware, optimistic V4 market prefilter and quantity breakpoints.

All books are station/type/side-specific, sorted asks ascending and bids
descending. The upper bound ignores fees, route costs and minimum-fill limits
deliberately: it may overestimate but must not discard an executable trade.
No TOP-N truncation and no historical alerts are consulted.
"""
from __future__ import annotations

import math


def gross_depth_upper_bound(asks, bids) -> float:
    """Maximum positive pre-fee gross spread using BOTH actual order depths.

    The best-bid * total-sell-volume shortcut substantially overcounts buy-side
    liquidity. This greedy matching gives an optimistic gross ceiling because
    it ignores tax, hauling, min-volume restrictions and price slippage beyond
    the matched bids. It never substitutes Jita sell orders for Jita bids.
    """
    i = j = 0
    gross = 0.0
    aleft = bleft = 0
    while i < len(asks) and j < len(bids):
        a, b = asks[i], bids[j]
        if a.type_id != b.type_id or a.buy or not b.buy:
            raise ValueError("INVALID_MARKET_BOOK_SIDE_OR_TYPE")
        if a.price >= b.price:
            break
        if not aleft:
            aleft = a.remaining
        if not bleft:
            bleft = b.remaining
        n = min(aleft, bleft)
        if n <= 0:
            raise ValueError("INVALID_MARKET_BOOK_DEPTH")
        gross += n * (b.price - a.price)
        aleft -= n
        bleft -= n
        if not aleft:
            i += 1
        if not bleft:
            j += 1
    return gross


def profitable_breakpoints(asks, bids, sales_tax: float) -> list[int]:
    """Integer quantities at every positive-after-tax matched order boundary.

    Used to evaluate variable-size lots instead of assuming all crossed units
    must be purchased. It does not perform the final policy/route check.
    """
    i = j = total = 0
    aleft = bleft = 0
    results = []
    while i < len(asks) and j < len(bids):
        a, b = asks[i], bids[j]
        if a.type_id != b.type_id or a.buy or not b.buy:
            raise ValueError("INVALID_MARKET_BOOK_SIDE_OR_TYPE")
        if a.price >= b.price * (1 - sales_tax):
            break
        if not aleft:
            aleft = a.remaining
        if not bleft:
            bleft = b.remaining
        n = min(aleft, bleft)
        if n <= 0:
            raise ValueError("INVALID_MARKET_BOOK_DEPTH")
        total += n
        results.append(total)
        aleft -= n
        bleft -= n
        if not aleft:
            i += 1
        if not bleft:
            j += 1
    return results


def candidate_quantities(asks, bids, sales_tax: float) -> list[int]:
    """Candidate lots include both normal and top-Jita-BUY-loss breakpoints.

    Preserve discounted source asks. Adding stressed BUY-depth boundaries
    prevents choosing a lot that requires more exit liquidity than remains
    if the best Jita bid disappears.
    """
    base = profitable_breakpoints(asks, bids, sales_tax)
    if not base:
        return []
    # Keep source asks intact: losing a cheap ask means no pre-purchase trade,
    # not a stranded inventory position. Model only a lost Jita top BUY order.
    stressed = profitable_breakpoints(
        asks, [b for b in bids if b.order_id != bids[0].order_id], sales_tax)
    maximal = base[-1]
    values = set(base)
    values.update(q for q in stressed if 0 < q <= maximal)
    # Include realistic min-fill crossing points, not only full order depth.
    for order in (*asks, *bids):
        if 1 < order.minimum <= maximal:
            values.add(order.minimum)
    values.add(1)
    return sorted(v for v in values if 0 < v <= maximal)
