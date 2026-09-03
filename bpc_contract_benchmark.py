from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from scanner_source import (
    PUBLIC_CONTRACTS_INDEX,
    DATA,
    LATEST,
    latest_file,
    download,
    load_contracts,
    truthy_series,
)

RANKED = LATEST / "ranked_opportunities.csv"
ALL_SCORED = LATEST / "all_executable_scored.csv"

MIN_EXACT_SAMPLES = 3


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def summarize(vals):
    vals = pd.to_numeric(pd.Series(vals), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    vals = vals[vals > 0]
    if vals.empty:
        return {"n": 0, "avg": np.nan, "median": np.nan, "p25": np.nan, "p75": np.nan}
    return {
        "n": int(len(vals)),
        "avg": float(vals.mean()),
        "median": float(vals.median()),
        "p25": float(vals.quantile(0.25)),
        "p75": float(vals.quantile(0.75)),
    }


def main():
    ranked = read_csv(RANKED)
    if ranked.empty or "contract_id" not in ranked.columns:
        print("BPC benchmark: no ranked opportunities")
        return

    target_ids = set(pd.to_numeric(ranked["contract_id"], errors="coerce").dropna().astype(int))
    if not target_ids:
        print("BPC benchmark: no target contract IDs")
        return

    c_url, _ = latest_file(PUBLIC_CONTRACTS_INDEX)
    c_path = DATA / Path(c_url).name
    if not c_path.exists():
        download(c_url, c_path)
    contracts, items = load_contracts(c_path)

    contracts["contract_id"] = pd.to_numeric(contracts["contract_id"], errors="coerce").astype("Int64")
    contracts["price"] = pd.to_numeric(contracts["price"], errors="coerce").fillna(0.0)
    valid_contracts = contracts[(contracts["type"] == "item_exchange") & (contracts["price"] > 0)].copy()
    valid_ids = set(valid_contracts["contract_id"].dropna().astype(int))

    items["contract_id"] = pd.to_numeric(items["contract_id"], errors="coerce").astype("Int64")
    items["type_id"] = pd.to_numeric(items["type_id"], errors="coerce").fillna(0).astype(int)
    items["runs"] = pd.to_numeric(items.get("runs", 0), errors="coerce").fillna(0).astype(int)
    items["material_efficiency"] = pd.to_numeric(items.get("material_efficiency", 0), errors="coerce").fillna(0).astype(int)
    items["time_efficiency"] = pd.to_numeric(items.get("time_efficiency", 0), errors="coerce").fillna(0).astype(int)
    items["_included"] = truthy_series(items["is_included"])
    items["_bpc"] = truthy_series(items["is_blueprint_copy"])

    # Identify the blueprint type and research state for every pushed opportunity.
    target_rows = items[items["contract_id"].isin(target_ids) & items["_included"] & items["_bpc"] & (items["runs"] > 0)].copy()
    if target_rows.empty:
        print("BPC benchmark: target contracts contain no BPC rows")
        return

    target_bp_types = set(target_rows["type_id"].astype(int))

    # Comparable universe: pure BPC sale contracts only, with no requested items and no non-BPC included items.
    relevant = items[items["contract_id"].isin(valid_ids)].copy()
    requested_contracts = set(relevant.loc[~relevant["_included"], "contract_id"].dropna().astype(int))
    non_bpc_included = set(relevant.loc[relevant["_included"] & ~relevant["_bpc"], "contract_id"].dropna().astype(int))
    pure_ids = valid_ids - requested_contracts - non_bpc_included
    pure_bpc = relevant[
        relevant["contract_id"].isin(pure_ids)
        & relevant["_included"]
        & relevant["_bpc"]
        & relevant["type_id"].isin(target_bp_types)
        & (relevant["runs"] > 0)
    ].copy()

    price_map = valid_contracts.set_index("contract_id")["price"].to_dict()
    comparable_records = []
    for cid, g in pure_bpc.groupby("contract_id", sort=False):
        cid = int(cid)
        # A benchmark contract must contain exactly one blueprint TYPE. Multiple copies are fine.
        all_inc = relevant[(relevant["contract_id"] == cid) & relevant["_included"]]
        bpc_inc = all_inc[all_inc["_bpc"]]
        types = set(bpc_inc["type_id"].astype(int))
        if len(types) != 1:
            continue
        bp_tid = next(iter(types))
        if bp_tid not in target_bp_types:
            continue
        total_runs = int(pd.to_numeric(bpc_inc["runs"], errors="coerce").fillna(0).clip(lower=0).sum())
        if total_runs <= 0:
            continue
        price = float(price_map.get(cid, 0) or 0)
        if price <= 0:
            continue
        me_values = set(pd.to_numeric(bpc_inc["material_efficiency"], errors="coerce").fillna(0).astype(int))
        te_values = set(pd.to_numeric(bpc_inc["time_efficiency"], errors="coerce").fillna(0).astype(int))
        me = next(iter(me_values)) if len(me_values) == 1 else None
        te = next(iter(te_values)) if len(te_values) == 1 else None
        comparable_records.append({
            "contract_id": cid,
            "bp_type_id": bp_tid,
            "me": me,
            "te": te,
            "total_runs": total_runs,
            "price_per_run": price / total_runs,
        })

    comps = pd.DataFrame(comparable_records)
    if comps.empty:
        print("BPC benchmark: no comparable pure-BPC contracts")
        return

    enriched = ranked.copy()
    columns = [
        "bpc_benchmark_type_id", "bpc_benchmark_me", "bpc_benchmark_te",
        "bpc_market_sample_count", "bpc_market_avg_per_run", "bpc_market_median_per_run",
        "bpc_market_p25_per_run", "bpc_market_p75_per_run", "bpc_market_basis",
        "bpc_current_cost_per_run", "bpc_discount_vs_avg", "bpc_discount_vs_median",
        "bpc_contract_market_value_est", "bpc_intrinsic_value_surplus",
    ]
    for col in columns:
        enriched[col] = np.nan if col != "bpc_market_basis" else ""

    by_target = {int(cid): g for cid, g in target_rows.groupby("contract_id", sort=False)}
    for idx, r in enriched.iterrows():
        try:
            cid = int(float(r["contract_id"]))
        except Exception:
            continue
        tg = by_target.get(cid)
        if tg is None or tg.empty:
            continue
        bp_types = set(tg["type_id"].astype(int))
        if len(bp_types) != 1:
            continue
        bp_tid = next(iter(bp_types))
        total_runs = int(pd.to_numeric(tg["runs"], errors="coerce").fillna(0).clip(lower=0).sum())
        if total_runs <= 0:
            continue
        me_values = set(tg["material_efficiency"].astype(int))
        te_values = set(tg["time_efficiency"].astype(int))
        me = next(iter(me_values)) if len(me_values) == 1 else None
        te = next(iter(te_values)) if len(te_values) == 1 else None

        same_type = comps[(comps["bp_type_id"] == bp_tid) & (comps["contract_id"] != cid)]
        exact = same_type
        if me is not None and te is not None:
            exact = same_type[(same_type["me"] == me) & (same_type["te"] == te)]

        exact_stats = summarize(exact["price_per_run"])
        all_stats = summarize(same_type["price_per_run"])
        if exact_stats["n"] >= MIN_EXACT_SAMPLES:
            stats = exact_stats
            basis = f"same_type_ME{me}_TE{te}"
        else:
            stats = all_stats
            basis = "same_type_all_ME_TE"
        if stats["n"] <= 0:
            continue

        current_per_run = float(r.get("contract_price", 0) or 0) / total_runs
        avg = stats["avg"]
        median = stats["median"]
        market_value = avg * total_runs if np.isfinite(avg) else np.nan
        surplus = market_value - float(r.get("contract_price", 0) or 0) if np.isfinite(market_value) else np.nan

        enriched.at[idx, "bpc_benchmark_type_id"] = bp_tid
        enriched.at[idx, "bpc_benchmark_me"] = me if me is not None else np.nan
        enriched.at[idx, "bpc_benchmark_te"] = te if te is not None else np.nan
        enriched.at[idx, "bpc_market_sample_count"] = stats["n"]
        enriched.at[idx, "bpc_market_avg_per_run"] = avg
        enriched.at[idx, "bpc_market_median_per_run"] = median
        enriched.at[idx, "bpc_market_p25_per_run"] = stats["p25"]
        enriched.at[idx, "bpc_market_p75_per_run"] = stats["p75"]
        enriched.at[idx, "bpc_market_basis"] = basis
        enriched.at[idx, "bpc_current_cost_per_run"] = current_per_run
        enriched.at[idx, "bpc_discount_vs_avg"] = current_per_run / avg - 1 if avg > 0 else np.nan
        enriched.at[idx, "bpc_discount_vs_median"] = current_per_run / median - 1 if median > 0 else np.nan
        enriched.at[idx, "bpc_contract_market_value_est"] = market_value
        enriched.at[idx, "bpc_intrinsic_value_surplus"] = surplus

    enriched.to_csv(RANKED, index=False)

    # Keep the detailed scored file consistent when it exists.
    scored = read_csv(ALL_SCORED)
    if not scored.empty and "contract_id" in scored.columns:
        bench_cols = ["contract_id"] + columns
        right = enriched[bench_cols].drop_duplicates("contract_id")
        scored = scored.drop(columns=[c for c in columns if c in scored.columns], errors="ignore")
        scored = scored.merge(right, on="contract_id", how="left")
        scored.to_csv(ALL_SCORED, index=False)

    have = int(pd.to_numeric(enriched["bpc_market_sample_count"], errors="coerce").fillna(0).gt(0).sum())
    print(f"BPC benchmark: enriched {have}/{len(enriched)} ranked opportunities")


if __name__ == "__main__":
    main()
