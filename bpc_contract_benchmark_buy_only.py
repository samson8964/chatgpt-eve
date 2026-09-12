from __future__ import annotations

import os

import pandas as pd

import bpc_contract_benchmark as bench
from scanner_source import fetch_many_ref, name_en

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


def is_skin_record(record, type_objs):
    tid = int(record.get("bp_type_id") or 0)
    name = name_en(type_objs.get(tid), "").lower()
    title = str(record.get("title", "") or "").lower()
    text = f" {name} {title} "
    return any(k in text for k in SKIN_KEYWORDS)


def main():
    original_builder = bench.build_pure_bpc_records

    def filtered_builder(contracts, items):
        c = contracts.copy()
        price = pd.to_numeric(c.get("price"), errors="coerce").fillna(float("inf"))
        c = c[price <= MAX_CONTRACT_PRICE].copy()
        records = original_builder(c, items)
        tids = {int(r.get("bp_type_id") or 0) for r in records if int(r.get("bp_type_id") or 0) > 0}
        type_objs = fetch_many_ref("types", tids) if tids else {}
        kept = [r for r in records if not is_skin_record(r, type_objs)]
        print(
            f"BPC benchmark policy: records={len(records)} kept={len(kept)} "
            f"removed_skin={len(records)-len(kept)} max_contract={MAX_CONTRACT_PRICE:.0f}"
        )
        return kept

    try:
        bench.build_pure_bpc_records = filtered_builder
        bench.main()
    finally:
        bench.build_pure_bpc_records = original_builder


if __name__ == "__main__":
    main()
