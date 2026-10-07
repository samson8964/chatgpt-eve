from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

SOURCE = Path("results/latest/ranked_opportunities.csv")
STATE = Path("results/state/bpc_fast_probe_seen.csv")
MIN_JITA_PROFIT = float(os.getenv("BPC_FAST_MIN_JITA_PROFIT", "50000000"))
MIN_JITA_ROI = float(os.getenv("BPC_FAST_MIN_JITA_ROI", "0.10"))


def _truth(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v or "").strip().lower() in {"1", "true", "t", "yes", "y"}


def _write_output(key: str, value: str) -> None:
    path = os.getenv("GITHUB_OUTPUT", "").strip()
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def main() -> None:
    if not SOURCE.exists():
        print("BPC fast probe: no baseline output")
        _write_output("trigger_deep", "false")
        _write_output("new_count", "0")
        return

    try:
        df = pd.read_csv(SOURCE)
    except pd.errors.EmptyDataError:
        df = pd.DataFrame()

    if df.empty:
        _write_output("trigger_deep", "false")
        _write_output("new_count", "0")
        return

    for col in ["contract_id", "jita_manufacturing_net_profit", "jita_manufacturing_net_roi"]:
        if col not in df.columns:
            print(f"BPC fast probe: missing {col}")
            _write_output("trigger_deep", "false")
            _write_output("new_count", "0")
            return

    candidate = df[
        df.get("jita_manufacturing_cost_complete", False).apply(_truth)
        & (pd.to_numeric(df["jita_manufacturing_net_profit"], errors="coerce").fillna(float("-inf")) >= MIN_JITA_PROFIT)
        & (pd.to_numeric(df["jita_manufacturing_net_roi"], errors="coerce").fillna(float("-inf")) >= MIN_JITA_ROI)
    ].copy()

    candidate["contract_id"] = pd.to_numeric(candidate["contract_id"], errors="coerce")
    candidate = candidate[candidate["contract_id"].notna()].copy()
    candidate["contract_id"] = candidate["contract_id"].astype("int64")
    candidate = candidate[candidate["contract_id"] > 0]

    if STATE.exists():
        try:
            old = pd.read_csv(STATE)
        except pd.errors.EmptyDataError:
            old = pd.DataFrame()
    else:
        old = pd.DataFrame()

    seen = set(pd.to_numeric(old.get("contract_id", pd.Series(dtype=float)), errors="coerce").dropna().astype("int64").tolist())
    fresh = candidate[~candidate["contract_id"].isin(seen)].copy()
    now = pd.Timestamp.now(tz="UTC").isoformat()

    rows = []
    if not old.empty:
        rows.extend(old.to_dict("records"))
    for _, r in fresh.iterrows():
        rows.append({
            "contract_id": int(r["contract_id"]),
            "first_seen_at": now,
            "snapshot_jita_profit": float(r["jita_manufacturing_net_profit"]),
            "snapshot_jita_roi": float(r["jita_manufacturing_net_roi"]),
            "blueprints": str(r.get("blueprints", "") or ""),
            "products": str(r.get("products", "") or ""),
        })

    STATE.parent.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(rows, columns=[
        "contract_id", "first_seen_at", "snapshot_jita_profit", "snapshot_jita_roi", "blueprints", "products"
    ])
    if not out.empty:
        out.drop_duplicates(subset=["contract_id"], keep="first", inplace=True)
        out.sort_values("first_seen_at", ascending=False, inplace=True)
        out = out.head(5000)
    out.to_csv(STATE, index=False)

    ids = ",".join(str(int(x)) for x in fresh["contract_id"].tolist())
    print(
        f"BPC fast probe: potential={len(candidate)} new={len(fresh)} "
        f"threshold=Jita {MIN_JITA_PROFIT/1e6:.0f}M/{MIN_JITA_ROI:.0%}"
    )
    if ids:
        print(f"BPC fast probe new contract ids: {ids}")

    _write_output("trigger_deep", "true" if len(fresh) else "false")
    _write_output("new_count", str(len(fresh)))
    _write_output("new_ids", ids)


if __name__ == "__main__":
    main()
