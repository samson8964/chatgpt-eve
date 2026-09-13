from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

DEALS = Path("results/latest/contract_deals.csv")
BPC = Path("results/latest/ranked_opportunities.csv")
BPC_VALUE = Path("results/latest/bpc_value_opportunities.csv")
BPC_V2 = Path("results/latest/ranked_opportunities_v2.csv")

SPOT_MIN_PROFIT = float(os.getenv("MAIL_SPOT_MIN_PROFIT", "30000000"))
SPOT_MIN_ROI = float(os.getenv("MAIL_SPOT_MIN_ROI", "0.10"))

BPC_VALUE_MIN_SAMPLES = int(os.getenv("MAIL_BPC_VALUE_MIN_SAMPLES", "5"))
BPC_VALUE_MIN_AVG_DISCOUNT = float(os.getenv("MAIL_BPC_VALUE_MIN_AVG_DISCOUNT", "0.30"))
BPC_VALUE_MIN_MEDIAN_DISCOUNT = float(os.getenv("MAIL_BPC_VALUE_MIN_MEDIAN_DISCOUNT", "0.20"))
BPC_VALUE_MIN_SURPLUS = float(os.getenv("MAIL_BPC_VALUE_MIN_SURPLUS", "20000000"))
BPC_MFG_MIN_PROFIT = float(os.getenv("MAIL_BPC_MFG_MIN_PROFIT", "20000000"))
BPC_MFG_MIN_ROI = float(os.getenv("MAIL_BPC_MFG_MIN_ROI", "0.10"))
BPC_V2_ENABLED = os.getenv("MAIL_BPC_V2_ENABLED", "1").strip().lower() not in {"0", "false", "no"}


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def finite(v, default=0.0):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def truth(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "t", "yes", "y"}


def prepare_spot(df: pd.DataFrame):
    if df.empty:
        return df

    eligible = []
    mail_profit = []
    mail_roi = []
    reasons = []
    has_v2_status = "execution_status" in df.columns

    for _, r in df.iterrows():
        status = str(r.get("execution_status", "SAFE") or "SAFE").upper()
        if has_v2_status and status != "SAFE":
            eligible.append(False)
            mail_profit.append(np.nan)
            mail_roi.append(np.nan)
            reasons.append(f"V2_STATUS_{status}")
            continue

        cls = str(r.get("deal_class", ""))
        is_a = cls.startswith("A")
        is_b = cls.startswith("B")

        if is_a:
            profit = finite(r.get("instant_net_profit"), 0.0)
            roi = finite(r.get("instant_net_roi"), 0.0)
            reason_ok = "A_V2_LIVE_BUY_ORDER" if has_v2_status else "A_INSTANT_BUY_ORDER"
        elif is_b:
            profit = finite(r.get("list_net_profit_est"), 0.0)
            roi = finite(r.get("list_net_roi_est"), 0.0)
            reason_ok = "B_LIST_ORDER"
        else:
            eligible.append(False)
            mail_profit.append(np.nan)
            mail_roi.append(np.nan)
            reasons.append("UNSUPPORTED_DEAL_CLASS")
            continue

        ok = profit >= SPOT_MIN_PROFIT and roi >= SPOT_MIN_ROI
        eligible.append(bool(ok))
        mail_profit.append(profit)
        mail_roi.append(roi)
        if ok:
            reasons.append(reason_ok)
        elif profit < SPOT_MIN_PROFIT:
            reasons.append("NET_PROFIT_BELOW_30M")
        else:
            reasons.append("ROI_BELOW_10PCT")

    df = df.copy()
    df["mail_net_profit"] = mail_profit
    df["mail_net_roi"] = mail_roi
    df["mail_eligible"] = eligible
    df["mail_filter_reason"] = reasons
    df.to_csv(DEALS, index=False)
    print(f"mail gate spot: eligible={int(pd.Series(eligible).sum())}/{len(df)}; SAFE-only={has_v2_status}")
    return df


def prepare_bpc_file(path: Path):
    """Legacy BPC mail gate retained for rollback/testing."""
    df = read_csv(path)
    if df.empty:
        return df

    eligible = []
    reasons = []
    intrinsic_signals = []
    manufacturing_signals = []
    value_gap = []

    for _, r in df.iterrows():
        n = int(finite(r.get("bpc_market_sample_count"), 0.0))
        davg = finite(r.get("bpc_discount_vs_avg"), np.nan)
        dmed = finite(r.get("bpc_discount_vs_median"), np.nan)
        surplus = finite(r.get("bpc_intrinsic_value_surplus"), 0.0)
        profit = finite(r.get("net_profit"), 0.0)
        roi = finite(r.get("net_roi"), 0.0)
        cap = finite(r.get("market_capacity_contracts"), 0.0)

        intrinsic_signal = (
            n >= BPC_VALUE_MIN_SAMPLES
            and math.isfinite(davg)
            and davg <= -BPC_VALUE_MIN_AVG_DISCOUNT
            and (not math.isfinite(dmed) or dmed <= -BPC_VALUE_MIN_MEDIAN_DISCOUNT)
            and surplus >= BPC_VALUE_MIN_SURPLUS
        )
        manufacturing_ok = profit >= BPC_MFG_MIN_PROFIT and roi >= BPC_MFG_MIN_ROI and cap >= 1
        ok = bool(intrinsic_signal or manufacturing_ok)
        eligible.append(ok)
        intrinsic_signals.append(bool(intrinsic_signal))
        manufacturing_signals.append(bool(manufacturing_ok))
        value_gap.append(max(0.0, surplus if intrinsic_signal else 0.0, profit if manufacturing_ok else 0.0))

        if intrinsic_signal and manufacturing_ok:
            reasons.append("INTRINSIC_VALUE_PLUS_MANUFACTURING")
        elif intrinsic_signal:
            reasons.append("INTRINSIC_VALUE")
        elif manufacturing_ok:
            reasons.append("MANUFACTURING")
        else:
            reasons.append("BELOW_BPC_MAIL_MARGIN")

    df = df.copy()
    df["bpc_intrinsic_signal"] = intrinsic_signals
    df["bpc_manufacturing_signal"] = manufacturing_signals
    df["mail_value_gap_isk"] = value_gap
    df["mail_eligible"] = eligible
    df["mail_filter_reason"] = reasons
    df.to_csv(path, index=False)
    print(
        f"mail gate {path.name}: eligible={int(pd.Series(eligible).sum())}/{len(df)}; "
        f"intrinsic={int(pd.Series(intrinsic_signals).sum())}; "
        f"manufacturing={int(pd.Series(manufacturing_signals).sum())}"
    )
    return df


def prepare_bpc_v2_gate():
    """Make the existing mail sender consume only strict V2 SAFE manufacturing opportunities.

    Intrinsic BPC value signals remain in their V2/watch files for analysis, but are deliberately
    not eligible for automatic mail because they are ask-price estimates rather than immediate
    executable profit.
    """
    base = read_csv(BPC)
    v2 = read_csv(BPC_V2)
    if base.empty:
        return base
    if v2.empty or "contract_id" not in v2.columns:
        raise RuntimeError("BPC V2 mail gate requires ranked_opportunities_v2.csv")

    v2_cols = [
        "contract_id",
        "v2_status",
        "v2_grade",
        "v2_score",
        "v2_live_net_profit",
        "v2_live_net_roi",
        "v2_stress_net_profit",
        "v2_orderbook_complete",
        "v2_product_slippage",
        "v2_material_max_slippage",
        "v2_est_fill_days",
        "v2_verified_at",
    ]
    v2_cols = [c for c in v2_cols if c in v2.columns]
    merged = base.merge(v2[v2_cols], on="contract_id", how="left", suffixes=("", "_v2mail"))

    statuses = merged.get("v2_status", pd.Series("", index=merged.index)).fillna("").astype(str)
    live_profit = pd.to_numeric(merged.get("v2_live_net_profit"), errors="coerce").fillna(0.0)
    live_roi = pd.to_numeric(merged.get("v2_live_net_roi"), errors="coerce").fillna(0.0)
    stress_profit = pd.to_numeric(merged.get("v2_stress_net_profit"), errors="coerce").fillna(0.0)
    complete = merged.get("v2_orderbook_complete", pd.Series(False, index=merged.index)).map(truth)

    manufacturing_ok = (
        statuses.eq("SAFE")
        & (live_profit >= BPC_MFG_MIN_PROFIT)
        & (live_roi >= BPC_MFG_MIN_ROI)
        & (stress_profit > 0)
        & complete
    )

    # The existing sender displays net_profit/net_roi/opportunity_score. Replace those display
    # fields with the live V2 values so the email cannot show stale baseline economics.
    merged["net_profit"] = live_profit
    merged["net_roi"] = live_roi
    if "v2_score" in merged.columns:
        merged["opportunity_score"] = pd.to_numeric(merged["v2_score"], errors="coerce").fillna(0.0)
    merged["bpc_intrinsic_signal"] = False
    merged["bpc_manufacturing_signal"] = manufacturing_ok.astype(bool)
    merged["mail_value_gap_isk"] = np.where(manufacturing_ok, live_profit, 0.0)
    merged["mail_eligible"] = manufacturing_ok.astype(bool)
    merged["mail_filter_reason"] = np.where(
        manufacturing_ok,
        "V2_SAFE_MANUFACTURING",
        "V2_NOT_SAFE_OR_BELOW_MARGIN",
    )
    merged.to_csv(BPC, index=False)

    value_df = read_csv(BPC_VALUE)
    if not value_df.empty:
        value_df = value_df.copy()
        value_df["bpc_intrinsic_signal"] = False
        value_df["bpc_manufacturing_signal"] = False
        value_df["mail_value_gap_isk"] = 0.0
        value_df["mail_eligible"] = False
        value_df["mail_filter_reason"] = "V2_VALUE_SIGNAL_WATCH_ONLY"
        value_df.to_csv(BPC_VALUE, index=False)

    print(
        f"mail gate BPC V2: SAFE manufacturing eligible={int(manufacturing_ok.sum())}/{len(merged)}; "
        "intrinsic value auto-mail disabled"
    )
    return merged


def main():
    prepare_spot(read_csv(DEALS))
    if BPC_V2_ENABLED:
        from runner_bpc_v2 import main as run_bpc_v2

        run_bpc_v2()
        prepare_bpc_v2_gate()
    else:
        prepare_bpc_file(BPC_VALUE)
        prepare_bpc_file(BPC)


if __name__ == "__main__":
    main()
