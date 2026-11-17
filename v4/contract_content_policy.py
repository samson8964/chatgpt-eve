"""Contract-only energy-turret crystal composition screen.

Use the SAME Jita 4-4 BUY-depth cash liquidation value that the contract
engine uses, not type-ID ranges, cargo volume or item counts.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

from v4.engine import fill_book

# EVE inventory groups (NOT blueprint groups or mining crystals).
ENERGY_TURRET_CRYSTAL_GROUP_IDS = frozenset({86, 374, 375})
CRYSTAL_MAJORITY_SHARE = 0.50
CONTRACT_MIN_NET_ISK = 50_000_000
CRYSTAL_SHARE_BASIS = "JITA_BUY_DEPTH_BY_INVENTORY_GROUP"


def energy_crystal_value_share(included: Mapping[int,int], books: Mapping,
                               catalog) -> float | None:
    """Return verified crystal share of included-item *cash exit* value.

    None means inventory group coverage, type quantity or Jita depth is
    unverified. Callers must NOT silently treat None as 0% crystals.
    """
    group_fn = getattr(catalog, "group_id", None)
    if not callable(group_fn) or not included:
        return None
    all_gross = crystal_gross = 0.0
    for key, amount in included.items():
        try:
            typ=int(key)
            qty=int(amount)
            group=group_fn(typ)
            if typ <= 0 or qty <= 0 or not isinstance(group,int) or group <= 0:
                return None
            fill=fill_book(books.get(typ, ()),qty)
            if fill.units != qty or not math.isfinite(fill.value) or fill.value < 0:
                return None
        except (ValueError, TypeError, OverflowError, AttributeError, KeyError):
            return None
        all_gross += fill.value
        if group in ENERGY_TURRET_CRYSTAL_GROUP_IDS:
            crystal_gross += fill.value
    if not math.isfinite(all_gross) or all_gross <= 0:
        return None
    return crystal_gross/all_gross


def eligible_contract_research(*, net_profit, roi, stress, cost,
                               crystal_share, category_required: bool,
                               partial_mode: bool=False) -> bool:
    """Ordinary contract research, with backwards-compatible legacy mode.

    Partial mode: full bundle purchase price, credited subset liquidation;
    stress is advisory (not gating); ROI strictly greater than 10%.
    """
    try:
        net=float(net_profit)
        ratio=float(roi)
        investment=float(cost)
        if not all(math.isfinite(n) for n in (net,ratio,investment)):
            return False
        if net < CONTRACT_MIN_NET_ISK or investment <= 0:
            return False
        if partial_mode:
            if ratio <= .10:
                return False
        else:
            stres=float(stress)
            if not math.isfinite(stres) or stres<=0 or ratio < .10:
                return False
    except (TypeError,ValueError,OverflowError):
        return False
    if crystal_share is None:
        return not category_required
    try:
        share=float(crystal_share)
    except (TypeError,ValueError,OverflowError):
        return False
    return math.isfinite(share) and 0 <= share < CRYSTAL_MAJORITY_SHARE
