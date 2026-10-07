from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

LATEST = Path("results/latest")
OUT = LATEST / "v3_shadow_comparison.md"


def read(path: str) -> pd.DataFrame:
    p = LATEST / path
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(p)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def ids(df: pd.DataFrame) -> set[int]:
    if df.empty or "contract_id" not in df.columns:
        return set()
    return set(pd.to_numeric(df["contract_id"], errors="coerce").dropna().astype(int))


def count_stage(df: pd.DataFrame, stage: str) -> int:
    if df.empty or "policy_stage" not in df.columns:
        return 0
    return int(df["policy_stage"].fillna("").astype(str).str.upper().eq(stage).sum())


def main():
    v2 = read("contract_deals.csv")
    full = read("v3_full_cash.csv")
    partial = read("v3_cash_floor.csv")
    barter = read("v3_barter.csv")
    listing = read("v3_conservative_listing.csv")
    research = read("v3_research.csv")

    v2_safe = v2
    if not v2.empty and "execution_status" in v2.columns:
        v2_safe = v2[v2["execution_status"].fillna("").astype(str).str.upper().eq("SAFE")].copy()

    v2_ids = ids(v2_safe)
    full_safe = full
    if not full.empty and "policy_stage" in full.columns:
        full_safe = full[full["policy_stage"].fillna("").astype(str).str.upper().isin({"SAFE", "MAIL"})].copy()
    full_ids = ids(full_safe)
    intersection = v2_ids & full_ids
    v2_only = v2_ids - full_ids
    v3_only = full_ids - v2_ids

    funnel_path = LATEST / "v3_rejection_funnel.json"
    funnel = {}
    if funnel_path.exists():
        try:
            funnel = json.loads(funnel_path.read_text("utf-8"))
        except Exception:
            funnel = {}

    lines = [
        "# V3 shadow comparison",
        "",
        "This is a non-production validation run. No mail is sent and no result is committed to main.",
        "",
        "## V2-equivalent FULL_CASH comparison",
        f"- V2 SAFE contracts: {len(v2_ids)}",
        f"- V3 FULL_CASH SAFE/MAIL contracts: {len(full_ids)}",
        f"- V3 FULL_CASH total rows: {len(full)}",
        f"- overlap: {len(intersection)}",
        f"- V2-only: {len(v2_only)}",
        f"- V3-only FULL_CASH: {len(v3_only)}",
        f"- V2 SAFE IDs: {sorted(v2_ids)}",
        f"- V3 FULL_CASH IDs: {sorted(full_ids)}",
        "",
        "## New V3 route counts",
        f"- PARTIAL_CASH_FLOOR rows: {len(partial)}",
        f"- BARTER rows: {len(barter)}",
        f"- LIST-SUPPORTED rows: {len(listing)}",
        f"- RESEARCH rows: {len(research)}",
        f"- formal MAIL decisions: {count_stage(full, 'MAIL') + count_stage(partial, 'MAIL') + count_stage(barter, 'MAIL')}",
        "",
        "## Rejection funnel",
        "~~~json",
        json.dumps(funnel, ensure_ascii=False, indent=2),
        "~~~",
    ]
    OUT.write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
