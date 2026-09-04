from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

DEALS = Path("results/latest/contract_deals.csv")
BPC = Path("results/latest/ranked_opportunities.csv")
BPC_VALUE = Path("results/latest/bpc_value_opportunities.csv")

# Spot mail: use current economics directly. No 5% Jita price haircut and no buy-coverage gate.
SPOT_MIN_PROFIT = float(os.getenv("MAIL_SPOT_MIN_PROFIT", "30000000"))
SPOT_MIN_ROI = float(os.getenv("MAIL_SPOT_MIN_ROI", "0.10"))

# BPC value track. Comparable contract asks are imperfect, so require several aligned signals.
BPC_VALUE_MIN_SAMPLES = int(os.getenv("MAIL_BPC_VALUE_MIN_SAMPLES", "5"))
BPC_VALUE_MIN_AVG_DISCOUNT = float(os.getenv("MAIL_BPC_VALUE_MIN_AVG_DISCOUNT", "0.30"))
BPC_VALUE_MIN_MEDIAN_DISCOUNT = float(os.getenv("MAIL_BPC_VALUE_MIN_MEDIAN_DISCOUNT", "0.20"))
BPC_VALUE_MIN_SURPLUS = float(os.getenv("MAIL_BPC_VALUE_MIN_SURPLUS", "20000000"))

# Manufacturing is a separate route into mail, not a prerequisite for BPC-value opportunities.
BPC_MFG_MIN_PROFIT = float(os.getenv("MAIL_BPC_MFG_MIN_PROFIT", "20000000"))
BPC_MFG_MIN_ROI = float(os.getenv("MAIL_BPC_MFG_MIN_ROI", "0.10"))


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


def prepare_spot(df: pd.DataFrame):
    if df.empty:
        return df

    eligible = []
    mail_profit = []
    mail_roi = []
    reasons = []

    for _, r in df.iterrows():
        cls = str(r.get("deal_class", ""))
        is_a = cls.startswith("A")
        is_b = cls.startswith("B")

        if is_a:
            profit = finite(r.get("instant_net_profit"), 0.0)
            roi = finite(r.get("instant_net_roi"), 0.0)
            reason_ok = "A_INSTANT_BUY_ORDER"
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
    print(f"mail gate spot: eligible={int(pd.Series(eligible).sum())}/{len(df)}")
    return df


def prepare_bpc_file(path: Path):
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

        # Either route may independently justify a mail. Manufacturing is no longer a veto.
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


def main():
    prepare_spot(read_csv(DEALS))
    prepare_bpc_file(BPC_VALUE)
    prepare_bpc_file(BPC)


if __name__ == "__main__":
    main()
