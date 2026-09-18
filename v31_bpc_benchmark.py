from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

import pandas as pd

ROOT = Path(".")
LATEST = Path("results/latest")
OUT = Path("results/v31-benchmark")
FILES = [
    "ranked_opportunities.csv",
    "all_executable_scored.csv",
    "product_watchlist.csv",
    "excluded.csv",
]


def run(label: str, cmd: list[str]) -> float:
    print(f"=== {label} ===")
    t0 = time.perf_counter()
    subprocess.run(cmd, check=True)
    elapsed = time.perf_counter() - t0
    print(f"{label} elapsed={elapsed:.2f}s")
    return elapsed


def snapshot(dst: Path):
    dst.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        src = LATEST / name
        if src.exists():
            shutil.copy2(src, dst / name)


def load(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def compare(v31_dir: Path, baseline_dir: Path):
    v = load(v31_dir / "ranked_opportunities.csv")
    b = load(baseline_dir / "ranked_opportunities.csv")
    report = {
        "v31_rows": int(len(v)),
        "baseline_rows": int(len(b)),
        "same_contract_set": False,
        "max_abs_profit_delta": None,
        "max_abs_roi_delta": None,
    }
    if v.empty and b.empty:
        report["same_contract_set"] = True
        return report
    if "contract_id" not in v.columns or "contract_id" not in b.columns:
        return report
    vids = set(pd.to_numeric(v["contract_id"], errors="coerce").dropna().astype(int))
    bids = set(pd.to_numeric(b["contract_id"], errors="coerce").dropna().astype(int))
    report["same_contract_set"] = vids == bids
    common = sorted(vids & bids)
    if not common:
        return report
    vv = v.copy()
    bb = b.copy()
    vv["contract_id"] = pd.to_numeric(vv["contract_id"], errors="coerce").astype("Int64")
    bb["contract_id"] = pd.to_numeric(bb["contract_id"], errors="coerce").astype("Int64")
    m = vv.merge(bb, on="contract_id", suffixes=("_v31", "_base"))
    if "net_profit_v31" in m and "net_profit_base" in m:
        report["max_abs_profit_delta"] = float(
            (pd.to_numeric(m["net_profit_v31"], errors="coerce") -
             pd.to_numeric(m["net_profit_base"], errors="coerce")).abs().max()
        )
    if "net_roi_v31" in m and "net_roi_base" in m:
        report["max_abs_roi_delta"] = float(
            (pd.to_numeric(m["net_roi_v31"], errors="coerce") -
             pd.to_numeric(m["net_roi_base"], errors="coerce")).abs().max()
        )
    return report


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    v31_dir = OUT / "v31"
    baseline_dir = OUT / "baseline"

    # V3.1 intentionally runs first from a cold process. Baseline then benefits from
    # already-downloaded static/reference data, so the timing comparison is conservative.
    v31_s = run("v3.1", ["python", "runner_buy_only_v31.py"])
    snapshot(v31_dir)

    baseline_s = run("baseline", ["python", "runner_buy_only.py"])
    snapshot(baseline_dir)

    result = compare(v31_dir, baseline_dir)
    result.update(
        {
            "v31_seconds": v31_s,
            "baseline_seconds": baseline_s,
            "speedup_x": baseline_s / v31_s if v31_s > 0 else None,
            "seconds_saved": baseline_s - v31_s,
        }
    )

    # Restore V3.1 outputs so artifacts represent the candidate engine under test.
    for name in FILES:
        src = v31_dir / name
        if src.exists():
            shutil.copy2(src, LATEST / name)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("V3.1 benchmark summary:")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # Same market snapshot + same economic rules should preserve the selected set.
    # Tiny fee/index movement is tolerated because the two live calls are sequential.
    if not result["same_contract_set"]:
        raise RuntimeError("V3.1 candidate contract set differs from baseline")
    if result["max_abs_roi_delta"] is not None and result["max_abs_roi_delta"] > 0.002:
        raise RuntimeError(f"V3.1 ROI drift too large: {result['max_abs_roi_delta']}")
    if result["max_abs_profit_delta"] is not None and result["max_abs_profit_delta"] > 5_000_000:
        raise RuntimeError(f"V3.1 profit drift too large: {result['max_abs_profit_delta']}")


if __name__ == "__main__":
    main()
