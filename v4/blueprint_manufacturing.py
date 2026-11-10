"""BPC-only theoretical manufacturing arbitrage; independent of instant order depth.

Pricing: the arithmetic average of the best FIVE DISTINCT Jita 4-4 price
levels, cheapest asks for every input and highest bids for finished outputs.
Fewer than five available levels use the observed levels and raise risk;
quantity/depth does not suppress valuation. These are *indicative* prices,
NOT a VWAP or a claim that all units can trade at the quoted average.

BPC uses licensed runs * copy quantity, never an arbitrary ten-run cap.
BPO and direct blueprint resale are excluded from this research pathway.
For a multi-BPC bundle, select ceil(30% of ALL eligible BPC entries) by
positive net manufacturing contribution, charge full contract price ONCE,
and never credit excluded/BPO/unpriced items. Reference manufacturing fees
come from ESI; any legacy fallback is marked unverified, not mail eligible.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

from v4.engine import Policy
from v4.catalog import blueprint_instance_kind

JITA = 60003760
INDUSTRY_FEE_RESERVE_RATE = .20
PRICE_LEVELS = 5
SELECT_FRACTION = .30
MAX_RUNS_PER_BLUEPRINT = 10_000_000  # safety limit for malformed source data


def _number(value):
    try:
        n = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return n if math.isfinite(n) else None


def _material_count(qty_per_run: int, runs: int, me: int):
    # CCP job-level material calculation; units-per-run-one items cannot vanish.
    if qty_per_run == 1:
        return runs
    return math.ceil(qty_per_run * runs * (1 - me / 100))


def top_five_levels(book, *, buy: bool):
    """Arithmetic mean of up to five DISTINCT positive levels, not quantity-VWAP."""
    prices = set()
    available = 0
    for order in book or ():
        price = _number(getattr(order, "price", None))
        remaining = getattr(order, "remaining", 0)
        if price is not None and price > 0 and int(remaining or 0) > 0:
            prices.add(price)
            available += int(remaining)
    levels = sorted(prices, reverse=buy)[:PRICE_LEVELS]
    if not levels:
        return None
    return {"unit_price": sum(levels) / len(levels),
            "price_levels": len(levels),
            "levels": levels,
            "available_units": available,
            "method": "TOP_5_DISTINCT_PRICE_LEVELS_ARITHMETIC_MEAN_NOT_VWAP"}


def _risk(prices: list[dict], *, fee_verified: bool, unknown_bpc_count: int = 0):
    """Transparent, bounded heuristic; lower is better. No liquidity guarantee."""
    score = 0.0
    flags = []
    if not fee_verified:
        score += 30
        flags.append("MANUFACTURING_FEE_NOT_ESI_VERIFIED")
    if unknown_bpc_count:
        score += min(15, unknown_bpc_count * 5)
        flags.append("BPC_VALUE_MISSING_IN_BUNDLE")
    for p in prices:
        if p["price_levels"] < PRICE_LEVELS:
            score += 7
            flags.append("LESS_THAN_FIVE_PRICE_LEVELS")
        required = p.get("required_units", 0)
        if required and p["available_units"] < required:
            score += 12
            flags.append("SNAPSHOT_DEPTH_BELOW_MODEL_QUANTITY")
    score = min(100.0, score)
    return round(score, 2), sorted(set(flags))


def evaluate_one(contract, blueprint_instance, recipe, jita_asks,
                 jita_bids, source_to_jita_haul, policy=Policy(), fee_context=None):
    """A BPC's manufacturing contribution, BEFORE full bundle contract price."""
    price = _number(contract.get("price"))
    if price is None or price <= 0:
        return None
    if blueprint_instance_kind(blueprint_instance.get("is_blueprint_copy"),
                                blueprint_instance.get("runs")) != "BPC":
        return None
    try:
        bp = int(blueprint_instance["type_id"])
        me = int(blueprint_instance["material_efficiency"])
        copies = int(blueprint_instance.get("quantity", 1))
        licensed = int(blueprint_instance["runs"])
    except (ValueError, TypeError, KeyError, OverflowError):
        return None
    if not (0 <= me <= 10) or copies <= 0 or licensed <= 0:
        return None
    total_runs = licensed * copies
    if total_runs > MAX_RUNS_PER_BLUEPRINT:
        return None
    if not isinstance(recipe, Mapping) or not recipe.get("materials") or not recipe.get("products"):
        return None
    if len(recipe["products"]) != 1:
        return None
    product_id_raw, units_raw = next(iter(recipe["products"].items()))
    try:
        product = int(product_id_raw)
        units_per_run = int(units_raw)
    except (ValueError, TypeError, OverflowError):
        return None
    if product <= 0 or units_per_run <= 0:
        return None
    total_products = units_per_run * total_runs
    output_quote = top_five_levels(jita_bids.get(product, ()), buy=True)
    if output_quote is None:
        return None
    output_quote["required_units"] = total_products
    input_quotes = []
    needed = {}
    material_paid = 0.0
    for mat_raw, count in recipe["materials"].items():
        try:
            mat = int(mat_raw)
            qty = _material_count(int(count), total_runs, me)
        except (ValueError, TypeError, OverflowError):
            return None
        if mat <= 0 or qty <= 0:
            return None
        input_quote = top_five_levels(jita_asks.get(mat, ()), buy=False)
        if input_quote is None:
            return None
        input_quote["required_units"] = qty
        input_quotes.append(input_quote)
        material_paid += qty * input_quote["unit_price"]
        needed[str(mat)] = qty
    haul = _number(source_to_jita_haul)
    if haul is None or haul < 0:
        return None
    fee_quote = fee_context.quote(recipe, total_runs) if fee_context is not None else None
    if fee_context is not None and fee_quote is None:
        return None
    manufacturing_fee = (fee_quote["manufacturing_fee_isk"] if fee_quote else
                         material_paid * INDUSTRY_FEE_RESERVE_RATE)
    gross = total_products * output_quote["unit_price"]
    sales_tax = gross * policy.sales_tax
    # Contract price and shipping charged ONCE at bundle level.
    contribution = gross - sales_tax - material_paid - manufacturing_fee
    risk_score, flags = _risk(
        input_quotes + [output_quote], fee_verified=fee_quote is not None)
    return {
        "kind": "blueprint_manufacturing",
        "contract_id": int(contract["contract_id"]),
        "blueprint_type_id": bp,
        "blueprint_kind": "BPC",
        "material_efficiency": me,
        "production_runs_assumed": total_runs,
        "product_type_id": product,
        "product_units": total_products,
        "product_gross_isk": gross,
        "material_cost_isk": material_paid,
        "manufacturing_fee_isk": manufacturing_fee,
        "manufacturing_fee_reserve_isk": manufacturing_fee,  # compatibility
        **(fee_quote or {}),
        "sales_tax_isk": sales_tax,
        "manufacturing_contribution_isk": contribution,
        "contract_price_isk": price,
        "haul_estimate_isk": haul,
        "required_materials": needed,
        "jita_material_ask_depth_verified_in_snapshot": False,
        "jita_product_buy_depth_verified_in_snapshot": False,
        "jita_material_top5_prices_observed": True,
        "jita_product_top5_prices_observed": True,
        "material_price_basis": "JITA_SELL_TOP_5_DISTINCT_LEVELS_SIMPLE_MEAN",
        "product_price_basis": "JITA_BUY_TOP_5_DISTINCT_LEVELS_SIMPLE_MEAN",
        "product_unit_price_estimate_isk": output_quote["unit_price"],
        "product_buy_price_level_count": output_quote["price_levels"],
        "material_sell_min_price_level_count": min(
            p["price_levels"] for p in input_quotes),
        "risk_score": risk_score,
        "risk_flags": flags,
        "facility_fee_status": (fee_quote["facility_fee_status"] if fee_quote else
            "20_PERCENT_MATERIAL_COST_RESERVE_NOT_FACILITY_VERIFIED"),
        "live_verified": False,
        "actionable": False,
    }


def evaluate_blueprint_contract(contract, instances: list[dict], recipes: Mapping,
                                markets: Mapping, source_to_jita_haul,
                                policy=Policy(), fee_context=None):
    """Rank all BPC entries, select top ceil(30%), charge FULL contract once."""
    price = _number(contract.get("price"))
    haul = _number(source_to_jita_haul)
    if price is None or price <= 0 or haul is None or haul < 0:
        return None
    # User excluded BPO contracts entirely, including mixed BPO/BPC bundles.
    kinds = [blueprint_instance_kind(x.get("is_blueprint_copy"), x.get("runs"))
             for x in instances]
    if "BPO" in kinds:
        return None
    valid_bpc = [x for x, kind in zip(instances, kinds) if kind == "BPC"]
    if not valid_bpc:  # BPO-only contract is never part of BPC research.
        return None
    possibilities = []
    for row in valid_bpc:
        try:
            typ = int(row["type_id"])
        except (ValueError, TypeError, KeyError, OverflowError):
            continue
        recipe = recipes.get(str(typ))
        if not isinstance(recipe, Mapping):
            continue
        mats = {int(t) for t in recipe.get("materials", {})}
        prod = {int(t) for t in recipe.get("products", {})}
        asks = {t: markets.get((JITA, t, False), []) for t in mats}
        bids = {t: markets.get((JITA, t, True), []) for t in prod}
        evaluation = evaluate_one(contract, row, recipe, asks, bids,
                                  haul, policy, fee_context)
        if evaluation is not None:
            possibilities.append(evaluation)
    if not possibilities:
        return None
    top_count = max(1, math.ceil(len(valid_bpc) * SELECT_FRACTION))
    selected = sorted(possibilities, key=lambda r: (
        -r["manufacturing_contribution_isk"], r["blueprint_type_id"]))[:top_count]
    # Never add a demonstrably negative contribution just to fill the quota.
    selected = [r for r in selected if r["manufacturing_contribution_isk"] > 0]
    if not selected:
        return None
    gross = sum(r["product_gross_isk"] for r in selected)
    materials = sum(r["material_cost_isk"] for r in selected)
    fees = sum(r["manufacturing_fee_isk"] for r in selected)
    taxes = sum(r["sales_tax_isk"] for r in selected)
    contribution = gross - materials - fees - taxes
    investment = price + materials + fees + haul
    net_profit = contribution - price - haul
    roi = net_profit / investment if investment > 0 else -1
    missing = len(valid_bpc) - len(possibilities)
    risk = min(100.0, max(r["risk_score"] for r in selected) +
               min(15, missing * 5))
    flags = sorted({flag for row in selected for flag in row["risk_flags"]} |
                   ({"BPC_VALUE_MISSING_IN_BUNDLE"} if missing else set()) |
                   ({"BUNDLE_SHARE_30_PERCENT_SELECTED"} if len(valid_bpc) > 1 else set()))
    strongest = selected[0]
    return {
        **strongest,
        "blueprint_type_id": strongest["blueprint_type_id"],
        "blueprint_kind": "BPC",
        "bundle_blueprint_total": len(valid_bpc),
        "bundle_blueprint_evaluated": len(possibilities),
        "bundle_blueprint_selected": len(selected),
        "bundle_selected_fraction": SELECT_FRACTION,
        "bundle_selected_type_ids": [r["blueprint_type_id"] for r in selected],
        "bundle_selected_details": [{
            "blueprint_type_id": r["blueprint_type_id"],
            "production_runs": r["production_runs_assumed"],
            "product_type_id": r["product_type_id"],
            "contribution_isk": r["manufacturing_contribution_isk"],
            "risk_score": r["risk_score"],
        } for r in selected],
        "product_gross_isk": gross,
        "material_cost_isk": materials,
        "manufacturing_fee_isk": fees,
        "manufacturing_fee_reserve_isk": fees,
        "sales_tax_isk": taxes,
        "manufacturing_contribution_isk": contribution,
        "contract_price_isk": price,
        "haul_estimate_isk": haul,
        "cost": investment,
        "net_profit": net_profit,
        "roi": roi,
        "risk_score": round(risk, 2),
        "risk_flags": flags,
        "policy_passed": net_profit >= policy.profit_floor and roi > policy.min_roi,
        "status": "WATCH",
        "reason": ("BLUEPRINT_BPC_TOP5_30PCT_ESI_FEE_RESEARCH_ONLY"
                   if fee_context is not None else
                   "BLUEPRINT_BPC_TOP5_30PCT_FEE_UNVERIFIED"),
        "model_candidate": net_profit >= policy.profit_floor and roi > policy.min_roi,
        "source_location": int(contract["start_location_id"]),
        "valuation_location_id": JITA,
        "destination_location": JITA,
        "valuation_basis": "JITA_TOP5_BPC_MANUFACTURE_30PCT_BUNDLE_ESTIMATE",
        "scenario_caveats": (
            "All licensed BPC runs; top-five distinct level arithmetic mean; "
            "depth not guaranteed; top ceil(30%) of BPC bundle, full contract cost; "
            "no BPO/resale/time/capital/sales-cycle value; not live executable."
        ),
    }
