"""Conservative partial-liquidation proof for a WHOLE item-exchange contract.

Buyer pays the full contract price, but may liquidate only a subset of cargo.
Other received items are left at pickup station and valued at exactly zero;
only credited cargo gets shipped to Jita. No blueprint/BPC is ever counted
as an ordinary market item. Uses only available Jita station BUY depth and
valid catalogue volume/group for credited goods.

Standalone engine for the new policy, retaining legacy engine.contract_proof
for backtests and explicit historical comparisons.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Callable

from v4.contract_content_policy import ENERGY_TURRET_CRYSTAL_GROUP_IDS
from v4.engine import Fill, Policy, fill_book


def _money(raw):
    try:
        n=float(raw)
    except (ValueError,TypeError,OverflowError):
        return None
    return n if math.isfinite(n) else None


def partial_cash_contract_proof(contract:Mapping, included:Mapping[int,int],
                                books:Mapping, catalog, haul_for_volume:Callable,
                                policy:Policy=Policy(), *,
                                min_profit=50_000_000, min_roi=.10):
    cid=int(contract["contract_id"])
    proof={
        "family":"contract:"+str(cid),"instance":"contract:"+str(cid),
        "kind":"contract","contract_id":cid,"status":"WATCH",
        "reason":"NO_JITA_BUY_LIQUIDITY_FOR_REGULAR_SUBSET",
        "partial_liquidation_basis":"JITA_CREDITED_REGULAR_BUY_DEPTH_IGNORED_CARGO_ZERO",
    }
    price=_money(contract.get("price"))
    if price is None or price<=0:
        return dict(proof,reason="INVALID_PRICE")
    if str(contract.get("type","")).lower()!="item_exchange" or not included:
        return dict(proof,reason="NON_CASH_EXCHANGE_OR_EMPTY")
    # credit each SKU at a depth-backed quantity, not necessarily the entire
    # contract quantity. Never value blueprint BPO/BPC at type-ID market price.
    candidates=[]
    group_missing=0
    blueprint_ignored=0
    no_bid=0
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
        bid_book=books.get(typ,())
        if not bid_book:
            no_bid+=1
            continue
        filled=fill_book(bid_book,qty)
        if filled.units<=0 or filled.value<=0:
            no_bid+=1
            continue
        # Stress is informative only, not required by the user's new ordinary
        # contract profit/ROI policy.
        stressed=fill_book([b for b in bid_book if b.order_id!=bid_book[0].order_id],
                           filled.units)
        candidates.append({
            "type_id":typ,"units":filled.units,"gross":filled.value,
            "m3":volume*filled.units,"group":group,
            "orders":list(filled.order_ids),
            "stress":(stressed.value if stressed.units==filled.units else None),
        })
    proof.update(ignored_blueprint_types=blueprint_ignored,
                 ignored_unclassified_types=group_missing,
                 ignored_no_bid_types=no_bid,
                 ignored_invalid_types=other_ignored,
                 credited_type_candidates=len(candidates))
    if not candidates:
        return proof
    # In the absence of complete per-unit delivery fee pricing, a deterministic
    # value/volume prefix search maximizes viable documented margins. Each
    # prefix and each single-item option is evaluated with full contract cost.
    # No assumption is made that ignored cargo needs transport.
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
        stress_gross=(sum(x["stress"] for x in subset)
                      if all(x["stress"] is not None for x in subset) else None)
        stress_net=(stress_gross*(1-policy.sales_tax)-investment
                    if stress_gross is not None else None)
        evaluated={
            "gross":gross,"net_profit":net,"profit":net,"roi":roi,
            "cost":investment,"haul":haul,"haul_isk":haul,
            "haul_cost_estimate_isk":haul,
            "cargo_volume_m3":m3,
            "density":net/m3 if m3>0 else None,
            "stress_profit":stress_net,
            "energy_crystal_value_share":share,
            "energy_crystal_share_verified":True,
            "credited_items":{str(x["type_id"]):x["units"] for x in subset},
            "credited_jita_buy_order_ids":[oid for x in subset for oid in x["orders"]],
            "credited_type_count":len(subset),
            "credited_gross_isk":gross,
            "ignored_types_count":len(included)-len(subset),
        }
        # Preserve alternative that passes required profit & ROI, not
        # merely the highest net if it misses the ratio or laser screen.
        passed=(net>=min_profit and roi>min_roi and share<.50)
        evaluated["policy_passed"]=passed
        rank=(int(passed),net,roi)
        if best is None or rank>best[0]:
            best=(rank,evaluated)
    if best is None:
        return dict(proof,reason="HAUL_UNVERIFIED")
    result=best[1]
    valid=result["policy_passed"]
    reason=("FORMAL_GATE_PASSED" if valid else "BELOW_GATE_OR_STRESS")
    return dict(proof,**result,status="MAIL" if valid else "WATCH",reason=reason)
