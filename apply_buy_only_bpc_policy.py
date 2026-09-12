from __future__ import annotations

import math
import os
from pathlib import Path

import pandas as pd

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


def apply(path: Path):
    df = read_csv(path)
    if df.empty:
        return

    before = len(df)
    if "contract_price" in df.columns:
        price = pd.to_numeric(df["contract_price"], errors="coerce").fillna(float("inf"))
        df = df[price <= MAX_CONTRACT_PRICE].copy()

    if not df.empty:
        mask = df.apply(skin_related_row, axis=1)
        skin_removed = int(mask.sum())
        df = df[~mask].copy()
    else:
        skin_removed = 0

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
        f"skin_removed={skin_removed} max_contract={MAX_CONTRACT_PRICE:.0f}"
    )


def main():
    for path in FILES:
        apply(path)


if __name__ == "__main__":
    main()
