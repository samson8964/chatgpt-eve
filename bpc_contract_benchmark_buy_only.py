from __future__ import annotations

import os

import pandas as pd

import bpc_contract_benchmark as bench
from scanner_source import (
    fetch_many_ref,
    manufacturing_recipe,
    name_en,
    type_group_id,
)

MAX_CONTRACT_PRICE = float(os.getenv("DEAL_MAX_CONTRACT_PRICE", "5000000000"))
SKIN_KEYWORDS = (
    " skin",
    "skin ",
    "skinr",
    "nanocoating",
    "sequencing binder",
    "design element",
    "pattern projection",
    "pattern projector",
    "holographic",
)

# These are OUTPUT hull groups. We classify the product made by the blueprint, not merely
# the blueprint name, so Hel/Nyx/etc. are removed even when the contract title is blank.
CAPITAL_HULL_GROUPS = {
    "carrier",
    "dreadnought",
    "force auxiliary",
    "capital industrial ship",
    "lancer dreadnought",
    "supercarrier",
    "titan",
    "freighter",
    "jump freighter",
}

# Only structure hull/product groups are excluded. Structure modules/rigs are not rejected
# merely because their names contain the word "structure".
STRUCTURE_GROUP_KEYWORDS = (
    "citadel",
    "engineering complex",
    "refinery",
    "flex structure",
    "control tower",
    "assembly array",
    "mobile laboratory",
    "corporate hangar array",
    "storage silo",
    "reactor array",
    "moon mining",
    "sovereignty structure",
    "orbital infrastructure",
    "orbital construction platform",
)


def is_skin_record(record, type_objs):
    tid = int(record.get("bp_type_id") or 0)
    name = name_en(type_objs.get(tid), "").lower()
    title = str(record.get("title", "") or "").lower()
    text = f" {name} {title} "
    return any(k in text for k in SKIN_KEYWORDS)


def blueprint_product_ids(bp_tid, blueprint_objs):
    recipe = manufacturing_recipe(blueprint_objs.get(int(bp_tid)))
    if not recipe:
        return set()
    _, products = recipe
    return {int(tid) for tid in products}


def output_exclusion_reason(bp_tid, blueprint_objs, product_type_objs, group_objs):
    for product_tid in blueprint_product_ids(bp_tid, blueprint_objs):
        pobj = product_type_objs.get(int(product_tid))
        gid = type_group_id(pobj)
        group_name = name_en(group_objs.get(gid), "").strip().lower() if gid is not None else ""
        if group_name in CAPITAL_HULL_GROUPS:
            return "CAPITAL_HULL"
        if any(k in group_name for k in STRUCTURE_GROUP_KEYWORDS):
            return "STRUCTURE_HULL"
    return ""


def main():
    original_builder = bench.build_pure_bpc_records

    def filtered_builder(contracts, items):
        c = contracts.copy()
        price = pd.to_numeric(c.get("price"), errors="coerce").fillna(float("inf"))
        c = c[price <= MAX_CONTRACT_PRICE].copy()
        records = original_builder(c, items)

        bp_tids = {int(r.get("bp_type_id") or 0) for r in records if int(r.get("bp_type_id") or 0) > 0}
        bp_type_objs = fetch_many_ref("types", bp_tids) if bp_tids else {}
        blueprint_objs = fetch_many_ref("blueprints", bp_tids) if bp_tids else {}

        product_ids = set()
        for bp_tid in bp_tids:
            product_ids.update(blueprint_product_ids(bp_tid, blueprint_objs))
        product_type_objs = fetch_many_ref("types", product_ids) if product_ids else {}
        group_ids = {type_group_id(o) for o in product_type_objs.values()}
        group_ids.discard(None)
        group_objs = fetch_many_ref("groups", group_ids) if group_ids else {}

        kept = []
        removed_skin = 0
        removed_capital = 0
        removed_structure = 0
        for r in records:
            if is_skin_record(r, bp_type_objs):
                removed_skin += 1
                continue
            reason = output_exclusion_reason(
                int(r.get("bp_type_id") or 0),
                blueprint_objs,
                product_type_objs,
                group_objs,
            )
            if reason == "CAPITAL_HULL":
                removed_capital += 1
                continue
            if reason == "STRUCTURE_HULL":
                removed_structure += 1
                continue
            kept.append(r)

        print(
            f"BPC benchmark policy: records={len(records)} kept={len(kept)} "
            f"removed_skin={removed_skin} removed_capital={removed_capital} "
            f"removed_structure={removed_structure} max_contract={MAX_CONTRACT_PRICE:.0f}"
        )
        return kept

    try:
        bench.build_pure_bpc_records = filtered_builder
        bench.main()
    finally:
        bench.build_pure_bpc_records = original_builder


if __name__ == "__main__":
    main()
