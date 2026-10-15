"""V4: deterministic, source-backed execution proofs. No historical state inputs.

All opportunity instances are evaluated each run. History is consulted only
AFTER policy validation by the outbox consumer. All monetary values are ISK.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Mapping, Sequence

from v4.market_execution import candidate_quantities


@dataclass(frozen=True)
class Policy:
    profit_floor: float = 50_000_000
    min_roi: float = .10
    min_density: float = 2_000
    sales_tax: float = .03375  # legacy Accounting-5 baseline; profile must be verified
    high_value_floor: float = 500_000_000
    high_value_min_roi: float = .10
    high_value_max_capital: float = 8_000_000_000
    high_value_min_capital: float = 5_000_000_000


@dataclass(frozen=True)
class Order:
    order_id: int
    type_id: int
    location_id: int
    buy: bool
    price: float
    remaining: int
    minimum: int = 1
    range: str = 'station'

    @classmethod
    def parse(cls, source: Mapping) -> 'Order':
        o = cls(
            order_id=int(source['order_id']),
            type_id=int(source['type_id']),
            location_id=int(source['location_id']),
            buy=str(source['is_buy_order']).lower() in ('true', '1'),
            price=float(source['price']),
            remaining=int(source['volume_remain']),
            minimum=max(1, int(source.get('min_volume') or 1)),
            range=str(source.get('range') or 'station'))
        if o.order_id <= 0 or o.type_id <= 0 or o.location_id <= 0 or o.price <= 0 or not math.isfinite(o.price) or o.remaining <= 0:
            raise ValueError('invalid_market_order')
        return o


def parse_orders_strict(rows, *, source: str) -> list[Order]:
    """Parse EVERY input row or fail the whole shadow run; never silently drop orders.

    A partial order book can inflate apparent liquidity/return or hide candidates.
    Errors are counted, with bounded index/type diagnostics, not raw credentials.
    """
    parsed: list[Order] = []
    invalid = 0
    samples: list[str] = []
    for idx, row in enumerate(rows):
        try:
            parsed.append(Order.parse(row))
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            invalid += 1
            if len(samples) < 4:
                samples.append(f"{idx}:{type(exc).__name__}")
    if invalid:
        raise ValueError(f"INCOMPLETE_{source}_ORDER_BOOK:{invalid} invalid rows; samples={','.join(samples)}")
    return parsed


def _well_formed_zero_remaining(raw: Mapping) -> bool:
    """Zero remaining is non-tradable, not corrupt, only if other fields validate.

    Do not turn zero into a tradable order; temporary 1 is used solely to
    validate all the other Order.parse fields. Negative, fractional, missing
    volume or malformed economic fields remain quarantined.
    """
    if not isinstance(raw, Mapping):
        return False
    try:
        remaining = raw["volume_remain"]
        if isinstance(remaining, bool) or float(remaining) != 0.0:
            return False
        checked = dict(raw)
        checked["volume_remain"] = 1
        Order.parse(checked)
        return True
    except (ValueError, KeyError, TypeError, OverflowError):
        return False


def parse_orders_with_quarantine(rows, *, source: str) -> tuple[list[Order], list[dict]]:
    """Account for EVERY raw row: active orders or auditable non-active proofs.

    Well-formed zero-remaining rows produce SOURCE_ORDER_ZERO_REMAINING
    research proofs and are never tradable. All other malformed rows produce
    SOURCE_ORDER_INVALID and keep integrity PARTIAL until investigated.
    No past-seen IDs, top-N cap, or product blacklist are consulted.
    """
    valid: list[Order] = []
    rejected: list[dict] = []
    for idx, raw in enumerate(rows):
        try:
            valid.append(Order.parse(raw))
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            key=f'input:{source}:{idx}'
            zero_remaining = _well_formed_zero_remaining(raw)
            rejected.append(dict(
                instance=key, family=key,
                kind='input_non_actionable' if zero_remaining else 'input_integrity',
                status='RESEARCH',
                reason='SOURCE_ORDER_ZERO_REMAINING' if zero_remaining else 'SOURCE_ORDER_INVALID',
                source_lane=source, row_index=idx,
                error_type=type(exc).__name__ if not zero_remaining else None,
                error_detail=str(exc)[:160] if not zero_remaining else None,
                order_id_hint=str(raw.get('order_id',''))[:40] if isinstance(raw,Mapping) else None))
    return valid,rejected


def order_index(orders: Sequence[Order]) -> dict[tuple[int, int, bool], list[Order]]:
    """FULL unfiltered index: all locations/types, not just familiar markets."""
    result = defaultdict(list)
    for o in orders:
        result[(o.location_id, o.type_id, o.buy)].append(o)
    for (location, typ, buy), rows in result.items():
        rows.sort(key=lambda x: (-x.price if buy else x.price, x.order_id))
    return dict(result)


@dataclass(frozen=True)
class Fill:
    units: int
    value: float
    order_ids: tuple[int, ...]


def fill_book(orders: Sequence[Order], quantity: int) -> Fill:
    """Walk actual order depth; observe minimum volumes and never invent liquidity."""
    todo = int(quantity)
    value = 0.0
    seen = []
    for o in orders:
        if todo <= 0:
            break
        n = min(todo, o.remaining)
        if n < o.minimum:
            continue
        value += n * o.price
        todo -= n
        seen.append(o.order_id)
    return Fill(quantity - todo, value, tuple(seen))


def quarantine_snapshot_candidate(proof: dict) -> dict:
    """No snapshot-derived signal can enter the live-mail outbox.

    Raw EVE Ref snapshots may be useful as a first economic estimate, but
    eligibility must be established with direct, fresh ESI/order proof.
    """
    if proof.get("status") == "MAIL":
        proof["model_candidate"] = True
        proof["status"] = "WATCH"
        proof["reason"] = "LIVE_ORDER_AND_CONTRACT_NOT_REVALIDATED"
    return proof


def stable_id(*values) -> str:
    return hashlib.sha256(json.dumps(values, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def profitable_trade(asks: Sequence[Order], bids: Sequence[Order], policy: Policy, max_units: int | None = None):
    """Full level-by-level crossing; output exposure only for positive marginal units.

    Must be called with station-verified, reachable destination bids. Order-level
    inputs intentionally don't include alert history.
    """
    if not asks or not bids:
        return None
    i = j = 0
    ask_left = asks[0].remaining
    bid_left = bids[0].remaining
    paid = gross = 0.0
    amount = 0
    source_ids, exit_ids = [], []
    while i < len(asks) and j < len(bids):
        a, b = asks[i], bids[j]
        if a.type_id != b.type_id or a.buy or not b.buy:
            raise ValueError('invalid_book_sides_or_type')
        if a.price >= b.price * (1 - policy.sales_tax):
            break
        n = min(ask_left, bid_left)
        if max_units is not None:
            n = min(n, max_units - amount)
        if n <= 0:
            break
        if n < a.minimum or n < b.minimum:
            # Market min_volume unsupported at this depth => fail closed.
            return None
        paid += n * a.price
        gross += n * b.price
        amount += n
        if a.order_id not in source_ids:
            source_ids.append(a.order_id)
        if b.order_id not in exit_ids:
            exit_ids.append(b.order_id)
        ask_left -= n
        bid_left -= n
        if ask_left == 0:
            i += 1
            if i < len(asks):
                ask_left = asks[i].remaining
        if bid_left == 0:
            j += 1
            if j < len(bids):
                bid_left = bids[j].remaining
    if amount <= 0:
        return None
    return dict(units=amount, paid=paid, gross=gross,
                ask_ids=tuple(source_ids), bid_ids=tuple(exit_ids))


def market_proof(asks: Sequence[Order], bids: Sequence[Order], *, source_location: int,
                 destination_location: int, type_id: int, volume_m3: float | None,
                 haul_isk: float | None, policy: Policy = Policy(), allowed: bool = False,
                 fresh: bool = False, haul_for_units=None) -> dict:
    """Select best gate-passing executable lot, using the same quantity both sides.

    Source asks remain fixed in stress; the best Jita buy order is removed.
    Stressed net must exceed the normal profit floor, not merely be positive.
    Route costs are re-evaluated for each lot through haul_for_units. Tested
    quantities cover crossed order boundaries, stressed-book boundaries and
    integer neighbours of economic-gate intersections. No top-N is applied.
    """
    family = 'market:%s:%s:%s' % (source_location, destination_location, type_id)
    base = dict(family=family, kind='market', source=source_location,
                destination=destination_location, type_id=type_id,
                policy='V4-depth-vwap', status='RESEARCH', reason='',
                instance=None, profit=None, roi=None, density=None)
    if not allowed:
        return dict(base, reason='SOURCE_OR_ROUTE_UNVERIFIED')
    if not fresh:
        return dict(base, reason='DATA_STALE_OR_PARTIAL')
    if volume_m3 is None or not math.isfinite(float(volume_m3)) or volume_m3 <= 0:
        return dict(base, reason='UNKNOWN_VOLUME')
    if haul_for_units is None and (haul_isk is None or
            not math.isfinite(float(haul_isk)) or float(haul_isk) < 0):
        return dict(base, reason='HAUL_UNVERIFIED')

    quantities = candidate_quantities(asks, bids, policy.sales_tax)
    if not quantities:
        return dict(base, reason='NO_PROFITABLE_MATCHED_DEPTH')
    evaluated = {}
    haul_unverified = False

    def evaluate(units: int):
        nonlocal haul_unverified
        if units in evaluated:
            return evaluated[units]
        matched = profitable_trade(asks, bids, policy, max_units=units)
        if not matched or matched['units'] != units:
            evaluated[units] = None
            return None
        try:
            haul = haul_for_units(units) if haul_for_units is not None else haul_isk
        except (ValueError, TypeError, OverflowError):
            haul = None
        if haul is None or not math.isfinite(float(haul)) or float(haul) < 0:
            haul_unverified = True
            evaluated[units] = None
            return None
        haul = float(haul)
        # The discounted source ask is the opportunity itself. If it vanishes,
        # abort before purchasing; it is not an inventory-risk stress scenario.
        # Stress ONLY Jita exit liquidity by removing the best BUY order.
        reduced_bids = [o for o in bids if o.order_id != bids[0].order_id]
        stressed = profitable_trade(asks, reduced_bids, policy, max_units=units)
        # An alternative trading fewer units is NOT a fallback for this lot.
        stress = (stressed['gross'] * (1 - policy.sales_tax)
                  - stressed['paid'] - haul
                  if stressed and stressed['units'] == units else -1)
        net = matched['gross'] * (1 - policy.sales_tax) - matched['paid'] - haul
        cost = matched['paid'] + haul
        roi = net / cost if cost > 0 else 0
        density = net / (units * volume_m3)
        if not all(math.isfinite(x) for x in (net, cost, roi, density, stress)):
            evaluated[units] = None
            return None
        margins = (net - policy.profit_floor,
                   net - policy.min_roi * cost,
                   net - policy.min_density * units * volume_m3,
                   stress - policy.profit_floor)
        # Exit-side stress must still clear the FULL profit floor, strictly.
        passed = all(x >= 0 for x in margins[:3]) and stress > policy.profit_floor
        result = dict(matched, cost=cost, profit=net, roi=roi, density=density,
                      stress_profit=stress, haul=haul, margins=margins,
                      passed=passed, source_vwap_isk_per_unit=matched['paid']/units,
                      jita_vwap_isk_per_unit=matched['gross']/units)
        evaluated[units] = result
        return result

    # Within each price-order segment, price*quantity, total haul, ROI and
    # stress gate margins are affine in quantity. Check adjacent integer
    # quantities around all constraint crossings, not only entire orders.
    for start, stop in zip(quantities, quantities[1:]):
        left, right = evaluate(start), evaluate(stop)
        if not left or not right or stop - start <= 1:
            continue
        for m0, m1 in zip(left['margins'], right['margins']):
            if m0 == m1 or m0 * m1 > 0:
                continue
            zero = start - m0 * (stop-start) / (m1-m0)
            if not math.isfinite(zero):
                continue
            for candidate in (math.floor(zero)-1, math.floor(zero),
                              math.ceil(zero), math.ceil(zero)+1):
                if start < candidate < stop:
                    evaluate(candidate)

    valid = [v for v in evaluated.values() if v is not None]
    if not valid:
        return dict(base, reason=('HAUL_UNVERIFIED' if haul_unverified
                                  else 'NO_PROFITABLE_MATCHED_DEPTH'))
    # Prefer the highest NET profit among lots meeting all existing gates;
    # if none pass, keep a watch-only economic trace (never email it).
    selected = max(valid, key=lambda v:(v['passed'],v['profit'],v['roi']))
    units = selected['units']
    identity = stable_id('market', source_location, destination_location, type_id,
                         selected['ask_ids'], selected['bid_ids'], units)
    status = 'MAIL' if selected['passed'] else 'WATCH'
    return dict(base, status=status,
                reason=('FORMAL_GATE_PASSED' if selected['passed']
                        else 'BELOW_GATE_OR_STRESS'),
                instance=identity, ask_order_ids=selected['ask_ids'],
                bid_order_ids=selected['bid_ids'], quantity=units,
                cost=selected['cost'], gross=selected['gross'],
                profit=selected['profit'], roi=selected['roi'],
                density=selected['density'], stress_profit=selected['stress_profit'],
                haul=selected['haul'], haul_isk=selected['haul'],
                source_vwap_isk_per_unit=selected['source_vwap_isk_per_unit'],
                jita_vwap_isk_per_unit=selected['jita_vwap_isk_per_unit'],
                executed_sell_cost=selected['paid'],
                executed_jita_buy_gross=selected['gross'],
                matched_depth_units=units, quantity_optimized=True)

def contract_proof(contract: Mapping, included: Mapping[int, int], books: Mapping[int, Sequence[Order]],
                   volumes: Mapping[int, float], *, policy: Policy = Policy(),
                   haul_isk: float | None, allowed: bool, fresh: bool,
                   item_classifications: Mapping[int, str] | None = None) -> dict:
    cid = int(contract['contract_id'])
    base = dict(family='contract:' + str(cid), instance='contract:' + str(cid), kind='contract',
                contract_id=cid, status='RESEARCH', reason='')
    if not allowed or not fresh:
        return dict(base, reason='ACCESS_UNVERIFIED_OR_STALE')
    price = float(contract.get('price') or 0)
    if not math.isfinite(price) or price <= 0:
        return dict(base, reason='INVALID_PRICE')
    if str(contract.get('type', '')).lower() != 'item_exchange' or not included:
        return dict(base, reason='NON_CASH_EXCHANGE_OR_EMPTY')
    if haul_isk is None or haul_isk < 0 or not math.isfinite(haul_isk):
        return dict(base, reason='HAUL_UNVERIFIED')
    # No BPO/BPC inference from type_id or ordinary order books: a blueprint
    # copy and original share type_id but cannot share the same liquidation value.
    # Without independently audited per-contract item classification, even a
    # rich-looking cash contract remains RESEARCH; never issue an alert.
    if not item_classifications or any(
        item_classifications.get(int(tid)) != 'regular' for tid in included
    ):
        return dict(base, reason='ITEM_CLASSIFICATION_UNVERIFIED_OR_BLUEPRINT')
    gross = volume = 0.0
    stress_gross: float | None = 0.0
    all_depth = True
    execution_ids = []
    for item_id, qty in included.items():
        v = volumes.get(item_id)
        if v is None or not math.isfinite(v) or v <= 0 or qty <= 0:
            return dict(base, reason='UNKNOWN_VOLUME_OR_ITEM')
        depth = books.get(item_id, ())
        f = fill_book(depth, qty)
        if f.units < qty:
            all_depth = False
        gross += f.value
        volume += v * qty
        execution_ids.extend(f.order_ids)
        # Strict full cash stress drops the single best order, requires full depth.
        remain = [o for o in depth if o.order_id != (depth[0].order_id if depth else -1)]
        st = fill_book(remain, qty)
        if st.units != qty:
            stress_gross = None
        elif stress_gross is not None:
            stress_gross += st.value
    if not all_depth:
        return dict(base, status='WATCH', reason='PARTIAL_CASH_FLOOR_RESEARCH', gross=gross)
    net = gross * (1 - policy.sales_tax) - price - haul_isk
    stress = (stress_gross * (1 - policy.sales_tax) - price - haul_isk
              if stress_gross is not None else None)
    investment = price + haul_isk
    roi = net / investment
    density = net / volume if volume > 0 else None
    # Invalid economic inputs are distinct from legitimate losses; never
    # encode inf/nan as profit or silently turn them into safe signals.
    if (not math.isfinite(net) or not math.isfinite(roi) or
            density is None or not math.isfinite(density) or
            (stress is not None and not math.isfinite(stress))):
        return dict(base, reason='NONFINITE_ECONOMICS')
    high_value = price > policy.high_value_min_capital
    capital_ok = not high_value or price <= policy.high_value_max_capital
    floor = policy.high_value_floor if high_value else policy.profit_floor
    roi_floor = policy.high_value_min_roi if high_value else policy.min_roi
    status = 'MAIL' if capital_ok and net >= floor and roi >= roi_floor and density >= policy.min_density and stress is not None and stress > 0 else 'WATCH'
    return dict(base, status=status, reason=('FORMAL_GATE_PASSED' if status == 'MAIL' else 'BELOW_GATE_OR_STRESS'),
                gross=gross, net_profit=net, profit=net, roi=roi, density=density,
                stress_profit=stress, cost=investment, exit_order_ids=tuple(execution_ids))
