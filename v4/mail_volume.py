"""Source-backed packaged cargo volumes for V4 research emails.

Only use quantities and item volumes stored in the exact same deep-scan proof.
Unknown volumes are NEVER presented as zero or silently added as if verified.
No ESI/network access, no re-valuation, no contract-gate changes.
"""
from __future__ import annotations

import math


def positive_volume(value):
    try:
        n=float(value)
    except (TypeError,ValueError,OverflowError):
        return None
    return n if math.isfinite(n) and n>0 else None


def format_m3(value) -> str:
    number=positive_volume(value)
    if number is None:
        return "未核实"
    if number >= 100:
        shown=f"{number:,.1f}"
    elif number >= 1:
        shown=f"{number:,.2f}"
    else:
        shown=f"{number:,.4f}"
    return shown.rstrip("0").rstrip(".") + " m³"


def market_volume(proof:dict, quantity:int) -> dict:
    """Selected market order volume; 1 unit must match stored total.

    The deep scanner recorded volume_m3 and cargo_volume_m3 when the order
    quantity was optimized. Do not recompute from current SDE or quote the
    volume of the entire sell book.
    """
    unit=positive_volume(proof.get("volume_m3"))
    total=positive_volume(proof.get("cargo_volume_m3"))
    try:
        n=int(quantity)
    except (ValueError,TypeError,OverflowError):
        n=0
    if not unit or n<=0:
        return {"unit_volume_m3":None,"transport_volume_m3":None}
    expected=unit*n
    if total is None or not math.isclose(expected,total,rel_tol=1e-8,abs_tol=1e-6):
        return {"unit_volume_m3":None,"transport_volume_m3":None}
    return {"unit_volume_m3":unit,"transport_volume_m3":total}


def contract_volume(proof:dict, included:dict, credited:dict) -> dict:
    """Credited subset transportation and whole-contract inventory footprint.

    Ignored gifts/blueprints are zero CASH value, not zero physical volume.
    The precomputed deep-scan transport volume must match the selected subset.
    If a type's static volume is unknown, the whole contract total is unknown.
    """
    unit_map=proof.get("included_volumes")
    if not isinstance(unit_map,dict):
        unit_map={}
    included=included if isinstance(included,dict) else {}
    credited=credited if isinstance(credited,dict) else {}

    def get_quantity(q):
        try:
            value=int(q)
            return value if value>0 and not isinstance(q,bool) else None
        except (TypeError,ValueError,OverflowError):
            return None

    exact_total=0.0
    known_minimum=0.0
    missing=0
    full_units={}
    for typ,quantity in included.items():
        key=str(typ)
        n=get_quantity(quantity)
        unit=positive_volume(unit_map.get(key))
        if n is None or unit is None:
            missing+=1
        else:
            subtotal=unit*n
            exact_total+=subtotal
            known_minimum+=subtotal
            full_units[key]=(n,unit,subtotal)

    details=[]
    credited_total=0.0
    credited_ok=bool(credited)
    for typ,quantity in credited.items():
        key=str(typ)
        n=get_quantity(quantity)
        source=full_units.get(key)
        if not n or not source or n>source[0]:
            credited_ok=False
            break
        unit=source[1]
        subtotal=unit*n
        credited_total+=subtotal
        details.append({"type_id":int(key),"quantity":n,
                        "unit_volume_m3":unit,"subtotal_volume_m3":subtotal})
    stored=positive_volume(proof.get("cargo_volume_m3"))
    if not (credited_ok and stored is not None and
            math.isclose(credited_total,stored,rel_tol=1e-8,abs_tol=1e-6)):
        credited_total=None
        details=[]
    return {
        "credited_transport_volume_m3":credited_total,
        "credited_volume_items":sorted(details,key=lambda x:x["subtotal_volume_m3"],reverse=True),
        "whole_contract_volume_m3":exact_total if included and not missing else None,
        "whole_contract_known_minimum_m3":known_minimum if full_units else None,
        "whole_contract_missing_volume_types":missing,
    }


def market_label(lead:dict) -> str:
    return ("体积 单件" + format_m3(lead.get("unit_volume_m3")) +
            " / 合计" + format_m3(lead.get("transport_volume_m3")))


def contract_label(lead:dict) -> str:
    transport=format_m3(lead.get("credited_transport_volume_m3"))
    full=lead.get("whole_contract_volume_m3")
    if positive_volume(full) is not None:
        whole=format_m3(full)
    else:
        minimum=positive_volume(lead.get("whole_contract_known_minimum_m3"))
        missed=int(lead.get("whole_contract_missing_volume_types") or 0)
        whole=("未核实（已知至少"+format_m3(minimum)+
               f"，另{missed}类缺体积）" if minimum and missed else "未核实")
    return "体积 计价货物"+transport+" / 整份合同"+whole


def credited_volume_breakdown(lead:dict, limit:int=3) -> str:
    """Single-line credited SKU units and m³ without filling the EVE mail."""
    items=lead.get("credited_volume_items") or []
    if not items:
        return ""
    result=[]
    for row in items[:max(0,limit)]:
        result.append("Type "+str(row["type_id"])+"×"+str(row["quantity"])+
                      " 单件"+format_m3(row["unit_volume_m3"])+
                      " 小计"+format_m3(row["subtotal_volume_m3"]))
    omitted=len(items)-max(0,limit)
    if omitted>0:
        result.append(f"另{omitted}类已计入合计")
    return "；".join(result)
