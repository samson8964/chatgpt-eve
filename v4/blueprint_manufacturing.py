"""Read-only conservative blueprint manufacturing research economics.

- BPC may consume at most its verified licensed runs.
- BPO gets a *bounded 10-run scenario*, never infinite free value.
- Entire CONTRACT price charged to EACH independently assessed blueprint option.
- All required materials bought from Jita 4-4 SELL depth.
- All resulting products sold to Jita 4-4 BUY depth.
- Material efficiency applies to the entire job; units required per run remain.
- Installation fee is a stated 20%-of-materials COST RESERVE, NOT a verified
  actual system/facility quote. Results are explicitly NON-ACTIONABLE ESTIMATES.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

from v4.engine import Policy, fill_book
from v4.catalog import blueprint_instance_kind

MAX_SCENARIO_RUNS=10
INDUSTRY_FEE_RESERVE_RATE=.20
JITA=60003760


def _number(value):
    try:
        n=float(value)
    except (ValueError,TypeError,OverflowError):
        return None
    return n if math.isfinite(n) else None


def _material_count(qty_per_run:int,runs:int,me:int):
    # CCP formula: material efficiency reduction calculated on whole job,
    # rounded up; required whole units per run are never eliminated.
    if qty_per_run==1:
        return runs
    return math.ceil(qty_per_run*runs*(1-me/100))


def evaluate_one(contract, blueprint_instance, recipe, jita_asks,
                 jita_bids, source_to_jita_haul, policy=Policy()):
    cid=int(contract["contract_id"])
    price=_number(contract.get("price"))
    if price is None or price<=0:
        return None
    bp=int(blueprint_instance["type_id"])
    kind=blueprint_instance_kind(blueprint_instance.get("is_blueprint_copy"),
                                 blueprint_instance.get("runs"))
    if kind=="UNKNOWN_BLUEPRINT":
        return None
    try:
        me=int(blueprint_instance["material_efficiency"])
        copies=int(blueprint_instance.get("quantity",1))
        licensed=int(blueprint_instance.get("runs",0))
    except (ValueError,TypeError,KeyError,OverflowError):
        return None
    if me<0 or me>10 or copies<=0:
        return None
    if kind=="BPC" and licensed<=0:
        return None
    potential=licensed*copies if kind=="BPC" else MAX_SCENARIO_RUNS
    scenario_runs=min(MAX_SCENARIO_RUNS,potential)
    if scenario_runs<=0:
        return None
    if not isinstance(recipe,dict) or not recipe.get("materials") or not recipe.get("products"):
        return None
    product_types=list(recipe["products"])
    if len(product_types)!=1:
        return None
    product=int(product_types[0])
    units_per_run=int(recipe["products"][product_types[0]])
    total_products=units_per_run*scenario_runs
    product_book=jita_bids.get(product,())
    if not product_book:
        return None
    product_fill=fill_book(product_book,total_products)
    if product_fill.units!=total_products:
        return None
    needed={}
    materials_paid=0.0
    for mat_raw,count in recipe["materials"].items():
        try:
            mat=int(mat_raw)
            qty=_material_count(int(count),scenario_runs,me)
        except (ValueError,TypeError,OverflowError):
            return None
        asks=jita_asks.get(mat,())
        if qty<=0 or not asks:
            return None
        fill=fill_book(asks,qty)
        if fill.units!=qty:
            return None
        materials_paid+=fill.value
        needed[str(mat)]=qty
    haul=_number(source_to_jita_haul)
    if haul is None or haul<0:
        return None
    # This is a transparent risk buffer, not the actual ESI industry system
    # cost-index and facility-tax quotation. Disclose in every emitted lead.
    fee_reserve=materials_paid*INDUSTRY_FEE_RESERVE_RATE
    investment=price+materials_paid+fee_reserve+haul
    gross=product_fill.value
    sale_tax=gross*policy.sales_tax
    net=gross-sale_tax-investment
    roi=net/investment if investment>0 else -1
    return {
        "kind":"blueprint_manufacturing",
        "contract_id":cid,
        "blueprint_type_id":bp,"blueprint_kind":kind,
        "material_efficiency":me,
        "production_runs_assumed":scenario_runs,
        "product_type_id":product,
        "product_units":total_products,
        "product_gross_isk":gross,
        "material_cost_isk":materials_paid,
        "manufacturing_fee_reserve_isk":fee_reserve,
        "sales_tax_isk":sale_tax,
        "contract_price_isk":price,
        "haul_estimate_isk":haul,
        "cost":investment,
        "net_profit":net,
        "roi":roi,
        "required_materials":needed,
        "facility_fee_status":"20_PERCENT_MATERIAL_COST_RESERVE_NOT_FACILITY_VERIFIED",
        "jita_product_buy_depth_verified_in_snapshot":True,
        "jita_material_ask_depth_verified_in_snapshot":True,
        "live_verified":False,
        "actionable":False,
        "policy_passed":net>=50_000_000 and roi>.10,
    }


def evaluate_blueprint_contract(contract, instances:list[dict], recipes:Mapping,
                                markets:Mapping, source_to_jita_haul,
                                policy=Policy()):
    """Conservatively pick strongest ONE blueprint, charging whole contract."""
    possibilities=[]
    for row in instances:
        typ=int(row["type_id"])
        recipe=recipes.get(str(typ))
        if not recipe:
            continue
        mats={int(t) for t in (recipe.get("materials") or {})}
        prod={int(t) for t in (recipe.get("products") or {})}
        asks={t:markets.get((JITA,t,False),[]) for t in mats}
        bids={t:markets.get((JITA,t,True),[]) for t in prod}
        result=evaluate_one(contract,row,recipe,asks,bids,source_to_jita_haul,policy)
        if result:
            possibilities.append(result)
    if not possibilities:
        return None
    best=max(possibilities,key=lambda x:(int(x["policy_passed"]),x["net_profit"],x["roi"]))
    return {**best,
            "status":"WATCH",
            "reason":"BLUEPRINT_MANUFACTURING_MODEL_ESTIMATE_FEE_UNVERIFIED",
            "model_candidate":best["policy_passed"],
            "source_location":int(contract["start_location_id"]),
            "valuation_location_id":JITA,
            "destination_location":JITA,
            "valuation_basis":"JITA_BUY_FINISHED_GOODS_JITA_SELL_MATERIALS_SNAPSHOT",
            "scenario_caveats":"BPO at most 10 runs; BPC limited by license, skills and slot time unverified, fees modelled with explicit reserve only."}
