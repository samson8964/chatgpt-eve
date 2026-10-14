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
                 fresh: bool = False) -> dict:
    """Evaluate ALL eligible books, return proof (including explicit rejection)."""
    family = 'market:%s:%s:%s' % (source_location, destination_location, type_id)
    base = dict(family=family, kind='market', source=source_location, destination=destination_location,
                type_id=type_id, policy='V4-1', status='RESEARCH',
                reason='', instance=None, profit=None, roi=None, density=None)
    if not allowed:
        return dict(base, reason='SOURCE_OR_ROUTE_UNVERIFIED')
    if not fresh:
        return dict(base, reason='DATA_STALE_OR_PARTIAL')
    if volume_m3 is None or not math.isfinite(float(volume_m3)) or volume_m3 <= 0:
        return dict(base, reason='UNKNOWN_VOLUME')
    if haul_isk is None or not math.isfinite(float(haul_isk)) or haul_isk < 0:
        return dict(base, reason='HAUL_UNVERIFIED')
    q = profitable_trade(asks, bids, policy)
    if not q:
        return dict(base, reason='NO_PROFITABLE_MATCHED_DEPTH')
    # Safety: loss of best execution levels must still be profitable. No fake depth.
    reduced_asks = [o for o in asks if o.order_id != q['ask_ids'][0]]
    reduced_bids = [o for o in bids if o.order_id != q['bid_ids'][0]]
    s = profitable_trade(reduced_asks, reduced_bids, policy)
    net = q['gross'] * (1 - policy.sales_tax) - q['paid'] - haul_isk
    stress = s['gross'] * (1 - policy.sales_tax) - s['paid'] - haul_isk if s else -1
    cost = q['paid'] + haul_isk
    roi = net / cost if cost > 0 else 0
    density = net / (q['units'] * volume_m3)
    identity = stable_id('market', source_location, destination_location, type_id,
                         q['ask_ids'], q['bid_ids'])
    status = 'MAIL' if (net >= policy.profit_floor and roi >= policy.min_roi and
                       density >= policy.min_density and stress > 0) else 'WATCH'
    return dict(base, status=status, reason=('FORMAL_GATE_PASSED' if status == 'MAIL' else 'BELOW_GATE_OR_STRESS'),
                instance=identity, ask_order_ids=q['ask_ids'], bid_order_ids=q['bid_ids'],
                quantity=q['units'], cost=cost, gross=q['gross'], profit=net, roi=roi,
                density=density, stress_profit=stress, haul=haul_isk)


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
