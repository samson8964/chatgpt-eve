from __future__ import annotations

import math
import os
from collections import defaultdict
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
    fetch_many_ref,
    name_en,
)
from contract_deal_scanner import (
    current_friendly_alliances,
    sovereignty_owners,
    load_structures,
    resolve_location,
)

RANKED = LATEST / "ranked_opportunities.csv"
ALL_SCORED = LATEST / "all_executable_scored.csv"
VALUE_RESULT = LATEST / "bpc_value_opportunities.csv"
VALUE_ALL = LATEST / "bpc_value_all.csv"

MIN_EXACT_SAMPLES = int(os.getenv("BPC_VALUE_MIN_EXACT_SAMPLES", "3"))
MIN_SAMPLES = int(os.getenv("BPC_VALUE_MIN_SAMPLES", "3"))
MIN_DISCOUNT = float(os.getenv("BPC_VALUE_MIN_DISCOUNT", "0.25"))
MIN_MEDIAN_DISCOUNT = float(os.getenv("BPC_VALUE_MIN_MEDIAN_DISCOUNT", "0.10"))
MIN_SURPLUS = float(os.getenv("BPC_VALUE_MIN_SURPLUS", "10000000"))
MIN_HOURS_TO_EXPIRE = float(os.getenv("BPC_VALUE_MIN_HOURS_TO_EXPIRE", "2"))
TOP = int(os.getenv("BPC_VALUE_TOP", "200"))

BENCH_COLUMNS = [
    "bpc_benchmark_type_id", "bpc_benchmark_me", "bpc_benchmark_te",
    "bpc_market_sample_count", "bpc_market_avg_per_run", "bpc_market_median_per_run",
    "bpc_market_p25_per_run", "bpc_market_p75_per_run", "bpc_market_basis",
    "bpc_current_cost_per_run", "bpc_discount_vs_avg", "bpc_discount_vs_median",
    "bpc_contract_market_value_est", "bpc_intrinsic_value_surplus",
]


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def finite(v, default=np.nan):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def robust_stats(values):
    vals = pd.to_numeric(pd.Series(list(values)), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    vals = vals[vals > 0]
    if vals.empty:
        return {"n": 0, "avg": np.nan, "median": np.nan, "p25": np.nan, "p75": np.nan}

    # Contract asks can contain extreme troll prices. For groups with enough samples,
    # remove only very remote IQR outliers, then compute the requested average price.
    if len(vals) >= 5:
        q1 = float(vals.quantile(0.25))
        q3 = float(vals.quantile(0.75))
        iqr = q3 - q1
        if iqr > 0:
            lo = max(0.0, q1 - 3.0 * iqr)
            hi = q3 + 3.0 * iqr
            cleaned = vals[(vals >= lo) & (vals <= hi)]
            if len(cleaned) >= 3:
                vals = cleaned

    return {
        "n": int(len(vals)),
        "avg": float(vals.mean()),
        "median": float(vals.median()),
        "p25": float(vals.quantile(0.25)),
        "p75": float(vals.quantile(0.75)),
    }


def group_stats_excluding(entries, current_contract_id):
    return robust_stats(v for cid, v in entries if int(cid) != int(current_contract_id))


def build_pure_bpc_records(contracts: pd.DataFrame, items: pd.DataFrame):
    contracts = contracts.copy()
    contracts["contract_id"] = pd.to_numeric(contracts["contract_id"], errors="coerce").astype("Int64")
    contracts["price"] = pd.to_numeric(contracts["price"], errors="coerce").fillna(0.0)
    contracts["start_location_id"] = pd.to_numeric(contracts.get("start_location_id"), errors="coerce").astype("Int64")

    valid = contracts[(contracts["type"] == "item_exchange") & (contracts["price"] > 0)].copy()
    now = pd.Timestamp.now(tz="UTC")
    if "date_expired" in valid.columns:
        exp = pd.to_datetime(valid["date_expired"], utc=True, errors="coerce")
        valid = valid[exp.isna() | (((exp - now).dt.total_seconds() / 3600) >= MIN_HOURS_TO_EXPIRE)].copy()
    valid_ids = set(valid["contract_id"].dropna().astype(int))

    ii = items[items["contract_id"].isin(valid_ids)].copy()
    ii["contract_id"] = pd.to_numeric(ii["contract_id"], errors="coerce").astype("Int64")
    for col, default in [("type_id", 0), ("runs", 0), ("material_efficiency", 0), ("time_efficiency", 0), ("quantity", 1)]:
        if col not in ii.columns:
            ii[col] = default
        ii[col] = pd.to_numeric(ii[col], errors="coerce").fillna(default).astype(int)
    ii["_included"] = truthy_series(ii["is_included"])
    ii["_bpc"] = truthy_series(ii["is_blueprint_copy"])

    requested = set(ii.loc[~ii["_included"], "contract_id"].dropna().astype(int))
    non_bpc_included = set(ii.loc[ii["_included"] & ~ii["_bpc"], "contract_id"].dropna().astype(int))
    pure_ids = valid_ids - requested - non_bpc_included
    pure = ii[
        ii["contract_id"].isin(pure_ids)
        & ii["_included"]
        & ii["_bpc"]
        & (ii["type_id"] > 0)
        & (ii["runs"] > 0)
    ].copy()

    c_by_id = valid.set_index("contract_id", drop=False)
    records = []
    for cid, g in pure.groupby("contract_id", sort=False):
        cid = int(cid)
        bp_types = set(g["type_id"].astype(int))
        # Fair per-run comparison is only clean when a contract contains one blueprint TYPE.
        # Multiple copies / different run counts of that same type are fine.
        if len(bp_types) != 1:
            continue
        bp_tid = next(iter(bp_types))
        copies = g["quantity"].clip(lower=1)
        total_runs = int((g["runs"].clip(lower=0) * copies).sum())
        if total_runs <= 0 or cid not in c_by_id.index:
            continue
        cm = c_by_id.loc[cid]
        if isinstance(cm, pd.DataFrame):
            cm = cm.iloc[0]
        price = finite(cm.get("price"), 0.0)
        if price <= 0:
            continue

        me_values = set(g["material_efficiency"].astype(int))
        te_values = set(g["time_efficiency"].astype(int))
        run_values = set(g["runs"].astype(int))
        me = next(iter(me_values)) if len(me_values) == 1 else None
        te = next(iter(te_values)) if len(te_values) == 1 else None
        per_copy_runs = next(iter(run_values)) if len(run_values) == 1 else None

        records.append({
            "contract_id": cid,
            "bp_type_id": bp_tid,
            "me": me,
            "te": te,
            "runs_per_copy": per_copy_runs,
            "bpc_copy_count": int(copies.sum()),
            "total_bpc_runs": total_runs,
            "contract_price": price,
            "price_per_run": price / total_runs,
            "start_location_id": int(cm.get("start_location_id")) if pd.notna(cm.get("start_location_id")) else 0,
            "contract_region_id_raw": int(cm.get("region_id")) if pd.notna(cm.get("region_id")) else 0,
            "contract_system_id_raw": int(cm.get("start_solar_system_id")) if "start_solar_system_id" in cm.index and pd.notna(cm.get("start_solar_system_id")) else 0,
            "date_expired": cm.get("date_expired", ""),
            "title": cm.get("title", ""),
        })
    return records


def attach_benchmarks(records):
    type_groups = defaultdict(list)
    exact_groups = defaultdict(list)
    for r in records:
        entry = (r["contract_id"], r["price_per_run"])
        type_groups[int(r["bp_type_id"])].append(entry)
        if r["me"] is not None and r["te"] is not None:
            exact_groups[(int(r["bp_type_id"]), int(r["me"]), int(r["te"]))].append(entry)

    out = []
    for r in records:
        cid = int(r["contract_id"])
        tid = int(r["bp_type_id"])
        exact_stats = {"n": 0}
        if r["me"] is not None and r["te"] is not None:
            exact_stats = group_stats_excluding(exact_groups[(tid, int(r["me"]), int(r["te"]))], cid)
        all_stats = group_stats_excluding(type_groups[tid], cid)

        if exact_stats.get("n", 0) >= MIN_EXACT_SAMPLES:
            stats = exact_stats
            basis = f"same_type_ME{r['me']}_TE{r['te']}"
        else:
            stats = all_stats
            basis = "same_type_all_ME_TE"

        rr = dict(r)
        rr.update({
            "bpc_benchmark_type_id": tid,
            "bpc_benchmark_me": r["me"] if r["me"] is not None else np.nan,
            "bpc_benchmark_te": r["te"] if r["te"] is not None else np.nan,
            "bpc_market_sample_count": int(stats.get("n", 0) or 0),
            "bpc_market_avg_per_run": stats.get("avg", np.nan),
            "bpc_market_median_per_run": stats.get("median", np.nan),
            "bpc_market_p25_per_run": stats.get("p25", np.nan),
            "bpc_market_p75_per_run": stats.get("p75", np.nan),
            "bpc_market_basis": basis,
            "bpc_current_cost_per_run": r["price_per_run"],
        })
        avg = finite(rr["bpc_market_avg_per_run"])
        med = finite(rr["bpc_market_median_per_run"])
        current = float(r["price_per_run"])
        rr["bpc_discount_vs_avg"] = current / avg - 1 if avg > 0 else np.nan
        rr["bpc_discount_vs_median"] = current / med - 1 if med > 0 else np.nan
        rr["bpc_contract_market_value_est"] = avg * r["total_bpc_runs"] if avg > 0 else np.nan
        rr["bpc_intrinsic_value_surplus"] = (
            rr["bpc_contract_market_value_est"] - r["contract_price"]
            if np.isfinite(rr["bpc_contract_market_value_est"])
            else np.nan
        )
        out.append(rr)
    return out


def significant_value_opportunity(r):
    n = int(finite(r.get("bpc_market_sample_count"), 0) or 0)
    davg = finite(r.get("bpc_discount_vs_avg"))
    dmed = finite(r.get("bpc_discount_vs_median"))
    surplus = finite(r.get("bpc_intrinsic_value_surplus"), 0.0)
    if n < MIN_SAMPLES or not np.isfinite(davg):
        return False
    if davg > -MIN_DISCOUNT:
        return False
    # Median is a guardrail against one or two absurdly high comparable asks inflating the mean.
    if np.isfinite(dmed) and dmed > -MIN_MEDIAN_DISCOUNT:
        return False
    return surplus >= MIN_SURPLUS


def value_score(r):
    davg = finite(r.get("bpc_discount_vs_avg"), 0.0)
    surplus = max(0.0, finite(r.get("bpc_intrinsic_value_surplus"), 0.0))
    samples = max(0.0, finite(r.get("bpc_market_sample_count"), 0.0))
    risk_rank = max(0.0, finite(r.get("risk_rank"), 5.0))
    discount_points = min(60.0, max(0.0, -davg) / 0.60 * 60.0)
    surplus_points = min(30.0, surplus / 200_000_000 * 30.0)
    sample_points = min(10.0, samples / 10.0 * 10.0)
    risk_adjust = {0: 5.0, 1: 3.0, 2: 0.0, 3: -3.0, 4: -6.0, 5: -8.0}.get(int(risk_rank), -8.0)
    return round(discount_points + surplus_points + sample_points + risk_adjust, 1)


def enrich_locations(candidates):
    if not candidates:
        return []
    loc_ids = sorted({int(r.get("start_location_id", 0) or 0) for r in candidates if int(r.get("start_location_id", 0) or 0) > 0})
    structures = load_structures([x for x in loc_ids if x >= 1_000_000_000_000])
    friendly_ids, own_id, own_name, own_ticker = current_friendly_alliances()
    sov_map = sovereignty_owners()

    location_cache = {}
    kept = []
    for r in candidates:
        lid = int(r.get("start_location_id", 0) or 0)
        if lid <= 0:
            continue
        if lid not in location_cache:
            location_cache[lid] = resolve_location(lid, structures, friendly_ids, sov_map)
        loc = location_cache[lid]
        # Location security is NOT a BPC filter. Only genuinely unresolved/unreachable systems are removed.
        if not loc or int(loc.get("system_id", 0) or 0) <= 0:
            continue
        if int(loc.get("shortest_jumps_to_jita", -1) or -1) < 0:
            continue
        rr = dict(r)
        rr.update(loc)
        rr["friendly_alliance_id"] = own_id
        rr["friendly_alliance_name"] = own_name
        rr["friendly_alliance_ticker"] = own_ticker
        rr["bpc_value_score"] = value_score(rr)
        kept.append(rr)
    return kept


def merge_manufacturing_context(value_rows, ranked):
    if ranked.empty or "contract_id" not in ranked.columns:
        return value_rows
    by_id = {}
    for _, row in ranked.iterrows():
        try:
            by_id[int(float(row["contract_id"]))] = row
        except Exception:
            pass
    out = []
    for r in value_rows:
        rr = dict(r)
        mr = by_id.get(int(r["contract_id"]))
        if mr is not None:
            for col in ranked.columns:
                if col in BENCH_COLUMNS or col == "contract_id":
                    continue
                val = mr.get(col)
                if col not in rr or rr.get(col) in (None, "") or (isinstance(rr.get(col), float) and np.isnan(rr.get(col))):
                    rr[col] = val
        out.append(rr)
    return out


def enrich_manufacturing_file(path: Path, benchmark_df: pd.DataFrame):
    target = read_csv(path)
    if target.empty or "contract_id" not in target.columns:
        return
    right = benchmark_df[["contract_id"] + BENCH_COLUMNS].drop_duplicates("contract_id")
    target = target.drop(columns=[c for c in BENCH_COLUMNS if c in target.columns], errors="ignore")
    target["contract_id"] = pd.to_numeric(target["contract_id"], errors="coerce").astype("Int64")
    right["contract_id"] = pd.to_numeric(right["contract_id"], errors="coerce").astype("Int64")
    target = target.merge(right, on="contract_id", how="left")
    target.to_csv(path, index=False)


def main():
    c_url, _ = latest_file(PUBLIC_CONTRACTS_INDEX)
    c_path = DATA / Path(c_url).name
    if not c_path.exists():
        download(c_url, c_path)
    contracts, items = load_contracts(c_path)

    records = build_pure_bpc_records(contracts, items)
    print(f"BPC value: pure single-type BPC contracts={len(records)}")
    benchmarked = attach_benchmarks(records)
    bench_df = pd.DataFrame(benchmarked)
    VALUE_ALL.parent.mkdir(parents=True, exist_ok=True)
    bench_df.to_csv(VALUE_ALL, index=False)

    # Keep manufacturing output enriched, but manufacturing is no longer the prerequisite
    # for a BPC to be considered a value opportunity.
    if not bench_df.empty:
        enrich_manufacturing_file(RANKED, bench_df)
        enrich_manufacturing_file(ALL_SCORED, bench_df)

    intrinsic = [r for r in benchmarked if significant_value_opportunity(r)]
    intrinsic = enrich_locations(intrinsic)

    # Resolve blueprint names only for the actual actionable shortlist.
    bp_ids = sorted({int(r["bp_type_id"]) for r in intrinsic})
    type_objs = fetch_many_ref("types", bp_ids) if bp_ids else {}
    for r in intrinsic:
        tid = int(r["bp_type_id"])
        r["blueprint_name"] = name_en(type_objs.get(tid), str(tid))
        if r.get("me") is not None and r.get("te") is not None:
            r["blueprints"] = f"{r['bpc_copy_count']}x {r['blueprint_name']} [{r['total_bpc_runs']} total runs, ME{int(r['me'])}/TE{int(r['te'])}]"
        else:
            r["blueprints"] = f"{r['bpc_copy_count']}x {r['blueprint_name']} [{r['total_bpc_runs']} total runs, mixed ME/TE]"

    ranked = read_csv(RANKED)
    intrinsic = merge_manufacturing_context(intrinsic, ranked)
    intrinsic.sort(
        key=lambda r: (
            float(r.get("bpc_value_score", 0) or 0),
            -float(r.get("bpc_discount_vs_avg", 0) or 0),
            float(r.get("bpc_intrinsic_value_surplus", 0) or 0),
        ),
        reverse=True,
    )
    value_df = pd.DataFrame(intrinsic[:TOP])
    value_df.to_csv(VALUE_RESULT, index=False)

    print(
        f"BPC value done: significant={len(intrinsic)} output={len(value_df)}; "
        f"threshold discount>={MIN_DISCOUNT*100:.0f}% median_guard>={MIN_MEDIAN_DISCOUNT*100:.0f}% "
        f"surplus>={MIN_SURPLUS/1e6:.0f}M samples>={MIN_SAMPLES}"
    )


if __name__ == "__main__":
    main()
