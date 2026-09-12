from __future__ import annotations

import math
import os
from pathlib import Path

import pandas as pd

from scanner_source import fetch_many_ref, manufacturing_recipe, name_en, type_group_id

LATEST = Path("results/latest")
MAX_CONTRACT_PRICE = float(os.getenv("DEAL_MAX_CONTRACT_PRICE", "5000000000"))

FILES = [
    LATEST / "ranked_opportunities.csv",
    LATEST / "all_executable_scored.csv",
    LATEST / "product_watchlist.csv",
    LATEST / "bpc_value_opportunities.csv",
    LATEST / "bpc_value_all.csv",
]

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


def finite(v, default=0.0):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def read_csv(path: Path):
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def skin_related_row(row) -> bool:
    text = " ".join(
        str(row.get(col, "") or "")
        for col in ("blueprint_name", "blueprints", "products", "title", "eve_contract_search_hint")
    ).lower()
    padded = f" {text} "
    return any(k in padded for k in SKIN_KEYWORDS)


def collect_type_ids(df):
    product_ids = set()
    bp_ids = set()
    if "product_type_id" in df.columns:
        product_ids.update(
            int(x)
            for x in pd.to_numeric(df["product_type_id"], errors="coerce").dropna().astype(int)
            if int(x) > 0
        )
    for col in ("bp_type_id", "bpc_benchmark_type_id"):
        if col in df.columns:
            bp_ids.update(
                int(x)
                for x in pd.to_numeric(df[col], errors="coerce").dropna().astype(int)
                if int(x) > 0
            )
    return product_ids, bp_ids


def build_exclusion_metadata(df):
    product_ids, bp_ids = collect_type_ids(df)
    blueprint_objs = fetch_many_ref("blueprints", bp_ids) if bp_ids else {}
    bp_products = {}
    for bp_tid in bp_ids:
        recipe = manufacturing_recipe(blueprint_objs.get(bp_tid))
        pids = set(recipe[1]) if recipe else set()
        bp_products[bp_tid] = {int(x) for x in pids}
        product_ids.update(bp_products[bp_tid])

    product_type_objs = fetch_many_ref("types", product_ids) if product_ids else {}
    group_ids = {type_group_id(o) for o in product_type_objs.values()}
    group_ids.discard(None)
    group_objs = fetch_many_ref("groups", group_ids) if group_ids else {}
    return bp_products, product_type_objs, group_objs


def product_reason(product_tid, product_type_objs, group_objs):
    pobj = product_type_objs.get(int(product_tid))
    gid = type_group_id(pobj)
    group_name = name_en(group_objs.get(gid), "").strip().lower() if gid is not None else ""
    if group_name in CAPITAL_HULL_GROUPS:
        return "CAPITAL_HULL"
    if any(k in group_name for k in STRUCTURE_GROUP_KEYWORDS):
        return "STRUCTURE_HULL"
    return ""


def row_output_reason(row, bp_products, product_type_objs, group_objs):
    product_ids = set()
    try:
        pid = int(float(row.get("product_type_id")))
        if pid > 0:
            product_ids.add(pid)
    except Exception:
        pass

    for col in ("bp_type_id", "bpc_benchmark_type_id"):
        try:
            bp_tid = int(float(row.get(col)))
        except Exception:
            continue
        product_ids.update(bp_products.get(bp_tid, set()))

    for pid in product_ids:
        reason = product_reason(pid, product_type_objs, group_objs)
        if reason:
            return reason
    return ""


def apply(path: Path):
    df = read_csv(path)
    if df.empty:
        return

    before = len(df)
    if "contract_price" in df.columns:
        price = pd.to_numeric(df["contract_price"], errors="coerce").fillna(float("inf"))
        df = df[price <= MAX_CONTRACT_PRICE].copy()

    if not df.empty:
        skin_mask = df.apply(skin_related_row, axis=1)
        skin_removed = int(skin_mask.sum())
        df = df[~skin_mask].copy()
    else:
        skin_removed = 0

    capital_removed = 0
    structure_removed = 0
    if not df.empty:
        bp_products, product_type_objs, group_objs = build_exclusion_metadata(df)
        reasons = df.apply(
            lambda row: row_output_reason(row, bp_products, product_type_objs, group_objs), axis=1
        )
        capital_removed = int((reasons == "CAPITAL_HULL").sum())
        structure_removed = int((reasons == "STRUCTURE_HULL").sum())
        df = df[~reasons.isin(["CAPITAL_HULL", "STRUCTURE_HULL"])].copy()

    # Manufacturing rows already derive gross_revenue by walking Jita buy-order depth.
    # Recompute profit from that executable revenue and explicitly remove broker/relist costs,
    # because an immediate sale into an existing buy order does not create a sell order.
    needed = {
        "gross_revenue",
        "contract_price",
        "material_cost_jita_depth",
        "manufacturing_job_cost",
        "sales_tax",
        "configured_haul_cost",
    }
    if needed.issubset(df.columns):
        gross = pd.to_numeric(df["gross_revenue"], errors="coerce").fillna(0.0)
        contract = pd.to_numeric(df["contract_price"], errors="coerce").fillna(0.0)
        mats = pd.to_numeric(df["material_cost_jita_depth"], errors="coerce").fillna(0.0)
        job = pd.to_numeric(df["manufacturing_job_cost"], errors="coerce").fillna(0.0)
        tax = pd.to_numeric(df["sales_tax"], errors="coerce").fillna(0.0)
        haul = pd.to_numeric(df["configured_haul_cost"], errors="coerce").fillna(0.0)
        net = gross - contract - mats - job - tax - haul
        base = contract + mats + job + haul
        df["net_profit"] = net
        df["net_roi"] = net / base.where(base > 0)
        df["market_broker_fee"] = 0.0
        df["relist_cost_reserve"] = 0.0
        df["valuation_basis"] = "JITA_BUY_DEPTH_ONLY"
        if "profit_per_serial_job_hour" in df.columns and "serial_job_hours" in df.columns:
            hours = pd.to_numeric(df["serial_job_hours"], errors="coerce").fillna(0.0)
            df["profit_per_serial_job_hour"] = net / hours.where(hours > 0)

    df.to_csv(path, index=False)
    print(
        f"buy-only BPC policy {path.name}: kept={len(df)}/{before} "
        f"skin_removed={skin_removed} capital_removed={capital_removed} "
        f"structure_removed={structure_removed} max_contract={MAX_CONTRACT_PRICE:.0f}"
    )


def main():
    for path in FILES:
        apply(path)


if __name__ == "__main__":
    main()
