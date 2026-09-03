from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

from scanner_source import (
    PUBLIC_CONTRACTS_INDEX,
    DATA,
    latest_file,
    download,
    load_contracts,
)

DEALS = Path("results/latest/contract_deals.csv")
BPC = Path("results/latest/ranked_opportunities.csv")
BPC_VALUE = Path("results/latest/bpc_value_opportunities.csv")

SPOT_STRESS_PRICE_DROP = float(os.getenv("MAIL_SPOT_STRESS_PRICE_DROP", "0.05"))
SPOT_MIN_STRESS_PROFIT = float(os.getenv("MAIL_SPOT_MIN_STRESS_PROFIT", "15000000"))
SPOT_MIN_STRESS_ROI = float(os.getenv("MAIL_SPOT_MIN_STRESS_ROI", "0.10"))
SPOT_MIN_BUY_COVERAGE = float(os.getenv("MAIL_SPOT_MIN_BUY_COVERAGE", "0.95"))

BPC_VALUE_MIN_SAMPLES = int(os.getenv("MAIL_BPC_VALUE_MIN_SAMPLES", "5"))
BPC_VALUE_MIN_AVG_DISCOUNT = float(os.getenv("MAIL_BPC_VALUE_MIN_AVG_DISCOUNT", "0.30"))
BPC_VALUE_MIN_MEDIAN_DISCOUNT = float(os.getenv("MAIL_BPC_VALUE_MIN_MEDIAN_DISCOUNT", "0.20"))
BPC_VALUE_MIN_SURPLUS = float(os.getenv("MAIL_BPC_VALUE_MIN_SURPLUS", "20000000"))
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


def freshness_score(age_hours):
    """Large bonus for newly issued contracts; old contracts rapidly lose mail priority."""
    if age_hours is None or not math.isfinite(age_hours) or age_hours < 0:
        return -40.0
    if age_hours <= 1:
        return 100.0
    if age_hours <= 3:
        return 80.0
    if age_hours <= 6:
        return 60.0
    if age_hours <= 12:
        return 40.0
    if age_hours <= 24:
        return 20.0
    if age_hours <= 48:
        return 0.0
    if age_hours <= 72:
        return -15.0
    return -30.0


def load_issue_map():
    c_url, _ = latest_file(PUBLIC_CONTRACTS_INDEX)
    c_path = DATA / Path(c_url).name
    if not c_path.exists():
        download(c_url, c_path)
    contracts, _ = load_contracts(c_path)
    if "contract_id" not in contracts.columns:
        return {}
    contracts["contract_id"] = pd.to_numeric(contracts["contract_id"], errors="coerce").astype("Int64")
    issue_col = "date_issued" if "date_issued" in contracts.columns else None
    if not issue_col:
        return {}
    out = {}
    for _, r in contracts[["contract_id", issue_col]].dropna(subset=["contract_id"]).iterrows():
        try:
            out[int(r["contract_id"])] = r[issue_col]
        except Exception:
            pass
    return out


def attach_freshness(df: pd.DataFrame, issue_map) -> pd.DataFrame:
    if df.empty or "contract_id" not in df.columns:
        return df
    now = pd.Timestamp.now(tz="UTC")
    issued = []
    ages = []
    scores = []
    for _, r in df.iterrows():
        try:
            cid = int(float(r["contract_id"]))
        except Exception:
            cid = 0
        raw = issue_map.get(cid, r.get("date_issued", ""))
        ts = pd.to_datetime(raw, utc=True, errors="coerce")
        if pd.isna(ts):
            age = np.nan
            issued.append("")
            ages.append(np.nan)
            scores.append(freshness_score(None))
        else:
            age = max(0.0, (now - ts).total_seconds() / 3600.0)
            issued.append(ts.isoformat())
            ages.append(age)
            scores.append(freshness_score(age))
    df = df.copy()
    df["date_issued"] = issued
    df["contract_age_hours"] = ages
    df["mail_freshness_score"] = scores
    return df


def prepare_spot(df: pd.DataFrame, issue_map):
    if df.empty:
        return df
    df = attach_freshness(df, issue_map)
    eligible = []
    stress_profit = []
    stress_roi = []
    reasons = []

    for _, r in df.iterrows():
        cls = str(r.get("deal_class", ""))
        if not cls.startswith("A"):
            eligible.append(False)
            stress_profit.append(np.nan)
            stress_roi.append(np.nan)
            reasons.append("MAIL_ONLY_INSTANT_BUY_ORDER_DEALS")
            continue

        gross = finite(r.get("jita_buy_gross"), 0.0)
        contract_price = finite(r.get("contract_price"), 0.0)
        haul = finite(r.get("haul_reserve"), 0.0)
        coverage = finite(r.get("buy_unit_coverage"), 0.0)
        tax_paid = finite(r.get("sales_tax_if_instant"), 0.0)
        tax_rate = tax_paid / gross if gross > 0 else 0.03375

        stressed_gross = gross * max(0.0, 1.0 - SPOT_STRESS_PRICE_DROP)
        stressed_tax = stressed_gross * max(0.0, tax_rate)
        net = stressed_gross - stressed_tax - contract_price - haul
        base = contract_price + haul
        roi = net / base if base > 0 else -1.0

        ok = True
        reason = "OK"
        if coverage < SPOT_MIN_BUY_COVERAGE:
            ok = False
            reason = "BUY_ORDER_COVERAGE_TOO_LOW"
        elif net < SPOT_MIN_STRESS_PROFIT:
            ok = False
            reason = "FAILS_5PCT_PRICE_STRESS_PROFIT"
        elif roi < SPOT_MIN_STRESS_ROI:
            ok = False
            reason = "FAILS_5PCT_PRICE_STRESS_ROI"

        eligible.append(ok)
        stress_profit.append(net)
        stress_roi.append(roi)
        reasons.append(reason)

    df["mail_stress_net_profit"] = stress_profit
    df["mail_stress_net_roi"] = stress_roi
    df["mail_eligible"] = eligible
    df["mail_filter_reason"] = reasons
    df.to_csv(DEALS, index=False)
    print(f"mail gate spot: eligible={int(pd.Series(eligible).sum())}/{len(df)}")
    return df


def prepare_bpc_file(path: Path, issue_map):
    df = read_csv(path)
    if df.empty:
        return df
    df = attach_freshness(df, issue_map)
    eligible = []
    reasons = []
    for _, r in df.iterrows():
        n = int(finite(r.get("bpc_market_sample_count"), 0.0))
        davg = finite(r.get("bpc_discount_vs_avg"), np.nan)
        dmed = finite(r.get("bpc_discount_vs_median"), np.nan)
        surplus = finite(r.get("bpc_intrinsic_value_surplus"), 0.0)
        profit = finite(r.get("net_profit"), 0.0)
        roi = finite(r.get("net_roi"), 0.0)
        cap = finite(r.get("market_capacity_contracts"), 0.0)

        intrinsic_ok = (
            n >= BPC_VALUE_MIN_SAMPLES
            and math.isfinite(davg)
            and davg <= -BPC_VALUE_MIN_AVG_DISCOUNT
            and (not math.isfinite(dmed) or dmed <= -BPC_VALUE_MIN_MEDIAN_DISCOUNT)
            and surplus >= BPC_VALUE_MIN_SURPLUS
        )
        manufacturing_ok = profit >= BPC_MFG_MIN_PROFIT and roi >= BPC_MFG_MIN_ROI and cap >= 1

        eligible.append(bool(intrinsic_ok or manufacturing_ok))
        if intrinsic_ok and manufacturing_ok:
            reasons.append("INTRINSIC_AND_MANUFACTURING")
        elif intrinsic_ok:
            reasons.append("INTRINSIC_VALUE")
        elif manufacturing_ok:
            reasons.append("MANUFACTURING")
        else:
            reasons.append("BELOW_STRICT_MAIL_MARGIN")

    df["mail_eligible"] = eligible
    df["mail_filter_reason"] = reasons
    df.to_csv(path, index=False)
    print(f"mail gate {path.name}: eligible={int(pd.Series(eligible).sum())}/{len(df)}")
    return df


def main():
    issue_map = load_issue_map()
    prepare_spot(read_csv(DEALS), issue_map)
    prepare_bpc_file(BPC_VALUE, issue_map)
    prepare_bpc_file(BPC, issue_map)


if __name__ == "__main__":
    main()
