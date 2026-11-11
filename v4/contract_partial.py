"""Ordinary cash-contract *research* without a Jita buy-depth hard gate.

Charge the FULL item-exchange contract price once. Credit only regular items;
all BPO/BPC/nonregular items have ZERO ordinary-resale value.

Each credited item uses, in order:
1. Full Jita 4-4 BUY depth fill: volume-weighted, executable *snapshot* quote.
2. Insufficient Jita BUY depth: quantity × average of up to five distinct best
   BUY price levels. Indicative (NOT an executable liquidation quote).
3. No Jita BUY orders: use ONLY the latest traded-day AVERAGE in the
   Forge REGION daily history (official ESI via EVE Ref cache, up to 90 days).
   The API has NO Jita station or individual last-transaction history.
4. Missing/stale Forge trade history: the item is unpriced (value zero).
   Never silently substitute Jita SELL asking prices as an exit value.

Research candidates are flagged with provenance and liquidity risk. Real-time
confirmation remains a separate, stricter process. Blueprint manufacturing is
a separate, mutually exclusive *valuation scenario* for the whole contract.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Callable

from v4.contract_content_policy import ENERGY_TURRET_CRYSTAL_GROUP_IDS
from v4.engine import Policy, fill_book
from v4.market_depth import top_price_levels

CONTRACT_REFERENCE_BASIS = (
    "JITA_REGULAR_BUY_OR_FORGE_REGIONAL_LAST_TRADED_DAY_AVG_RESEARCH"
)
CONTRACT_VALUATION_BASIS = "JITA_BUY_OR_FORGE_LATEST_TRADED_DAY_AVG_NOT_LIVE"


def _money(raw):
    try:
        n = float(raw)
    except (ValueError, TypeError, OverflowError):
        return None
    return n if math.isfinite(n) else None


def _estimate_regular_item(typ, qty, bid_book, ask_book, history_quote=None):
    """Return source-labelled research value, never manufacture missing orders."""
    if bid_book:
        filled = fill_book(bid_book, qty)
        if filled.units == qty and filled.value > 0:
            # The entire quantity is matched against source-recorded bids.
            return {
                "type_id":typ,"units":qty,"gross":filled.value,
                "price_source":"JITA_BUY_DEPTH_FULL_SNAPSHOT",
                "matched_buy_units":qty,"buy_order_ids":list(filled.order_ids),
                "stress":None, "liquidity_risk_flags":[],
            }
        top = top_price_levels(bid_book, buy=True)
        unit_price = _money(top["simple_mean_isk_per_unit"])
        if unit_price is not None and unit_price > 0:
            return {
                "type_id":typ,"units":qty,"gross":qty*unit_price,
                "price_source":"JITA_TOP5_BUY_LEVEL_MEAN_NOT_EXECUTABLE",
                "matched_buy_units":filled.units,"buy_order_ids":[],
                "stress":None,
                "liquidity_risk_flags":["JITA_BUY_DEPTH_INSUFFICIENT",
                                        "REFERENCE_QUOTE_NOT_EXECUTABLE"],
            }
    # No sellable bid exists. The region's last traded-day mean is a
    # labelled *research estimate*, NOT the last fill or a Jita station quote.
    if not bid_book and isinstance(history_quote, Mapping):
        unit_price = _money(history_quote.get("price"))
        trade_day = history_quote.get("date")
        age = history_quote.get("age_days")
        if (unit_price is not None and unit_price > 0
                and history_quote.get("region_id") == 10000002
                and isinstance(trade_day, str)
                and isinstance(age, int) and 1 <= age <= 90):
            return {
                "type_id":typ,"units":qty,"gross":qty*unit_price,
                "price_source":
                    "THE_FORGE_LAST_TRADED_DAY_AVG_NO_JITA_BUY_NOT_EXECUTABLE",
                "matched_buy_units":0,"buy_order_ids":[],
                "history_reference_date":trade_day,
                "history_reference_age_days":age,
                "history_reference_region_id":10000002,
                "history_reference_volume":history_quote.get("volume"),
                "stress":None,
                "liquidity_risk_flags":["NO_JITA_BUY_ORDERS",
                                        "FORGE_REGION_NOT_JITA_4_4_STATION",
                                        "DAILY_AVG_NOT_LAST_INDIVIDUAL_TRADE",
                                        "HISTORY_NOT_EXECUTABLE_SELL_PRICE"],
            }
    return None


def partial_cash_contract_proof(contract:Mapping, included:Mapping[int,int],
                                books:Mapping, catalog, haul_for_volume:Callable,
                                policy:Policy=Policy(), *,
                                ask_books:Mapping | None=None,
                                historical_quotes:Mapping | None=None,
                                min_profit=50_000_000, min_roi=.10):
    cid=int(contract["contract_id"])
    proof={
        "family":"contract:"+str(cid),"instance":"contract:"+str(cid),
        "kind":"contract","contract_id":cid,"status":"WATCH",
        "reason":"NO_JITA_REFERENCE_PRICE_FOR_REGULAR_SUBSET",
        "partial_liquidation_basis":CONTRACT_REFERENCE_BASIS,
    }
    price=_money(contract.get("price"))
    if price is None or price<=0:
        return dict(proof,reason="INVALID_PRICE")
    if str(contract.get("type","")).lower()!="item_exchange" or not included:
        return dict(proof,reason="NON_CASH_EXCHANGE_OR_EMPTY")

    asks_by_type=ask_books or {}
    history_by_type=historical_quotes or {}
    candidates=[]
    group_missing=0
    blueprint_ignored=0
    no_reference=0
    other_ignored=0
    for typ_raw,qty_raw in included.items():
        try:
            typ=int(typ_raw)
            qty=int(qty_raw)
        except (TypeError,ValueError,OverflowError):
            other_ignored+=1
            continue
        if typ<=0 or qty<=0:
            other_ignored+=1
            continue
        if catalog.classification(typ)=="blueprint_type":
            blueprint_ignored+=1
            continue
        if catalog.classification(typ)!="regular":
            group_missing+=1
            continue
        volume=_money(catalog.volume(typ))
        group=catalog.group_id(typ)
        if volume is None or volume<=0 or not isinstance(group,int) or group<=0:
            group_missing+=1
            continue
        candidate=_estimate_regular_item(
            typ,qty,books.get(typ,()),asks_by_type.get(typ,()),
            history_by_type.get(typ))
        if candidate is None:
            no_reference+=1
            continue
        candidate.update(m3=volume*qty,group=group)
        candidates.append(candidate)
    proof.update(ignored_blueprint_types=blueprint_ignored,
                 ignored_unclassified_types=group_missing,
                 ignored_no_bid_types=0,  # absent buys no longer hard-reject
                 ignored_no_reference_types=no_reference,
                 ignored_invalid_types=other_ignored,
                 credited_type_candidates=len(candidates))
    if not candidates:
        return proof

    # Subset search still charges full acquisition price per independent
    # strategy. Excluded cargo is neither valued nor assumed transported.
    candidates.sort(key=lambda x:(-x["gross"]/x["m3"],-x["gross"],x["type_id"]))
    subsets=[candidates[:n] for n in range(1,len(candidates)+1)]
    if len(candidates)>1:
        subsets.extend([[v] for v in candidates])
    best=None
    for subset in subsets:
        gross=sum(x["gross"] for x in subset)
        m3=sum(x["m3"] for x in subset)
        try:
            haul=_money(haul_for_volume(m3))
        except (ValueError,TypeError,OverflowError):
            haul=None
        if haul is None or haul<0:
            continue
        investment=price+haul
        net=gross*(1-policy.sales_tax)-investment
        roi=net/investment if investment>0 else -math.inf
        crystal=sum(x["gross"] for x in subset if
                    x["group"] in ENERGY_TURRET_CRYSTAL_GROUP_IDS)
        share=crystal/gross
        # Depth stress has no meaning for hypothetical, extrapolated quotes.
        stress_net=None
        risks=sorted({flag for item in subset
                      for flag in item["liquidity_risk_flags"]})
        history_total=sum(x["gross"] for x in subset if
                 x["price_source"]==
                 "THE_FORGE_LAST_TRADED_DAY_AVG_NO_JITA_BUY_NOT_EXECUTABLE")
        matched=sum(x["matched_buy_units"] for x in subset)
        estimated={
            "gross":gross,"net_profit":net,"profit":net,"roi":roi,
            "cost":investment,"haul":haul,"haul_isk":haul,
            "haul_cost_estimate_isk":haul,
            "cargo_volume_m3":m3,
            "density":net/m3 if m3>0 else None,
            "stress_profit":stress_net,
            "energy_crystal_value_share":share,
            "energy_crystal_share_verified":True,
            "credited_items":{str(x["type_id"]):x["units"] for x in subset},
            "credited_jita_buy_order_ids":[oid for x in subset
                                           for oid in x["buy_order_ids"]],
            "credited_type_count":len(subset),
            "credited_gross_isk":gross,
            "ignored_types_count":len(included)-len(subset),
            "ordinary_price_sources":{str(x["type_id"]):x["price_source"] for x in subset},
            "contract_liquidity_risk_flags":risks,
            "contract_ask_only_reference_share":0.0,
            "contract_history_reference_share":history_total/gross,
            "contract_history_reference_dates":{
                str(x["type_id"]):x["history_reference_date"]
                for x in subset if x.get("history_reference_date")},
            "jita_buy_depth_sufficient_for_credited_items":not risks,
            "matched_jita_buy_units":matched,
            "reference_pricing_not_live":True,
        }
        passed=(net>=min_profit and roi>min_roi and share<.50)
        estimated["policy_passed"]=passed
        rank=(int(passed),net,roi)
        if best is None or rank>best[0]:
            best=(rank,estimated)
    if best is None:
        return dict(proof,reason="HAUL_UNVERIFIED")
    result=best[1]
    reason="FORMAL_GATE_PASSED" if result["policy_passed"] else "BELOW_GATE_OR_STRESS"
    return dict(proof,**result,
                status="MAIL" if result["policy_passed"] else "WATCH",
                reason=reason)
