from __future__ import annotations

import math
import os
from pathlib import Path

import pandas as pd

MFG_SOURCE = Path("results/latest/ranked_opportunities_v2.csv")
VALUE_SOURCE = Path("results/latest/bpc_value_opportunities_v2.csv")
OUT = Path("results/latest/v3_bpc_opportunities.csv")
REPORT = Path("results/latest/v3_bpc_opportunities.md")

BPC_MFG_MIN_JITA_PROFIT = float(os.getenv("MAIL_BPC_MFG_MIN_JITA_PROFIT", "50000000"))
BPC_MFG_MIN_JITA_ROI = float(os.getenv("MAIL_BPC_MFG_MIN_JITA_ROI", "0.10"))


def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _num(v, default=0.0):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _truth(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v or "").strip().lower() in {"1", "true", "t", "yes", "y"}


def classify_manufacturing_row(r) -> tuple[str, bool, str]:
    """BPC mail gate: only the user's four Jita-manufacturing execution checks.

    1) Jita manufacturing net profit >= 50M
    2) Jita manufacturing ROI >= 10%
    3) Jita stress profit > 0
    4) material and product order-book depth complete

    The older remote-factory profit/ROI/stress thresholds and legacy SAFE/CHANGED
    label are analysis signals only and do not block an otherwise executable BPC.
    """
    jita_cost_complete = _truth(r.get("v2_jita_manufacturing_cost_complete"))
    jita_profit = _num(r.get("v2_jita_live_net_profit"), float("-inf"))
    jita_roi = _num(r.get("v2_jita_live_net_roi"), float("-inf"))
    jita_stress = _num(r.get("v2_jita_stress_net_profit"), float("-inf"))
    depth_complete = _truth(r.get("v2_orderbook_complete"))

    if not jita_cost_complete or not depth_complete:
        return "RESEARCH", False, "BPC_JITA_COST_OR_ORDERBOOK_INCOMPLETE"
    if jita_profit < BPC_MFG_MIN_JITA_PROFIT:
        return "WATCH", False, "BPC_JITA_PROFIT_BELOW_50M"
    if jita_roi < BPC_MFG_MIN_JITA_ROI:
        return "WATCH", False, "BPC_JITA_ROI_BELOW_10PCT"
    if jita_stress <= 0:
        return "WATCH", False, "BPC_JITA_STRESS_NOT_POSITIVE"
    return "MAIL", True, "BPC_JITA_4_GATE_PASSED"


def manufacturing_rows(df: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    if df.empty:
        return rows
    for _, r in df.iterrows():
        stage, mail_eligible, reason = classify_manufacturing_row(r)
        jita_complete = _truth(r.get("v2_jita_manufacturing_cost_complete"))
        jita_profit = _num(r.get("v2_jita_live_net_profit"), 0.0) if jita_complete else 0.0
        jita_roi = _num(r.get("v2_jita_live_net_roi"), 0.0) if jita_complete else 0.0
        jita_stress = _num(r.get("v2_jita_stress_net_profit"), 0.0) if jita_complete else 0.0
        try:
            cid = int(float(r.get("contract_id", 0)))
        except Exception:
            continue
        if cid <= 0:
            continue
        rows.append(
            {
                "engine_version": "Opportunity Engine V3",
                "channel": "BPC_MANUFACTURING",
                "contract_id": cid,
                "policy_stage": stage,
                "confidence_class": "BPC-MFG-STRICT",
                "mail_eligible": bool(mail_eligible),
                "policy_reason": reason,
                "execution_status": "SAFE" if stage in {"SAFE", "MAIL"} else stage,
                "opportunity_score": _num(r.get("v2_score"), 0.0),
                "score_grade": str(r.get("v2_grade", "") or ""),
                "net_profit": jita_profit,
                "net_roi": jita_roi,
                "stress_net_profit": jita_stress,
                "verified_at": str(r.get("v2_verified_at", "") or ""),
                "blueprints": str(r.get("blueprints", "") or ""),
                "products": str(r.get("products", "") or ""),
                "contract_price": _num(r.get("contract_price"), 0.0),
                "material_cost": _num(r.get("v2_live_material_cost"), 0.0),
                "jita_manufacturing_job_cost": _num(r.get("v2_jita_manufacturing_job_cost"), 0.0),
                "gross_revenue": _num(r.get("v2_live_gross_revenue"), 0.0),
                "sales_tax": _num(r.get("v2_live_sales_tax"), 0.0),
                "product_best_buy": _num(r.get("v2_product_best_buy"), 0.0),
                "product_vwap": _num(r.get("v2_product_vwap"), 0.0),
                "product_worst_buy": _num(r.get("v2_product_worst_buy"), 0.0),
                "product_slippage": _num(r.get("v2_product_slippage"), 0.0),
                "material_max_slippage": _num(r.get("v2_material_max_slippage"), 0.0),
                "estimated_fill_days": _num(r.get("v2_est_fill_days"), 999.0),
                "liquidity_score": _num(r.get("v2_liquidity_score"), 0.0),
                "capital_lock_days": _num(r.get("v2_capital_lock_days"), 0.0),
                "output_qty": _num(r.get("v2_live_output_qty"), _num(r.get("output_qty"), 0.0)),
                "product_type_id": _num(r.get("v2_live_product_type_id"), _num(r.get("product_type_id"), 0.0)),
                "total_bpc_runs": _num(r.get("total_bpc_runs"), 0.0),
                "factory_system": str(r.get("factory_system", "") or ""),
                "factory_station": str(r.get("factory_station", "") or ""),
                "date_expired": str(r.get("date_expired", "") or ""),
                "legacy_specialist_status": str(r.get("v2_status", "") or ""),
                "legacy_specialist_live_profit": _num(r.get("v2_live_net_profit"), 0.0),
                "legacy_specialist_live_roi": _num(r.get("v2_live_net_roi"), 0.0),
                "legacy_specialist_stress_profit": _num(r.get("v2_stress_net_profit"), 0.0),
            }
        )
    return rows


def intrinsic_rows(df: pd.DataFrame, manufacturing_contracts: set[int]) -> list[dict]:
    rows: list[dict] = []
    if df.empty:
        return rows
    for _, r in df.iterrows():
        if str(r.get("v2_value_status", "") or "").strip().upper() != "VALUE_SIGNAL":
            continue
        try:
            cid = int(float(r.get("contract_id", 0)))
        except Exception:
            continue
        if cid <= 0 or cid in manufacturing_contracts:
            continue
        rows.append(
            {
                "engine_version": "Opportunity Engine V3",
                "channel": "BPC_INTRINSIC_WATCH",
                "contract_id": cid,
                "policy_stage": "WATCH",
                "confidence_class": "BPC-COMPARABLE-ASKS",
                "mail_eligible": False,
                "policy_reason": "BPC_INTRINSIC_VALUE_NOT_EXECUTION_PROOF",
                "execution_status": "WATCH",
                "opportunity_score": _num(r.get("v2_value_score"), 0.0),
                "score_grade": "",
                "net_profit": 0.0,
                "net_roi": 0.0,
                "stress_net_profit": 0.0,
                "verified_at": "",
                "blueprints": str(r.get("blueprints", "") or ""),
                "products": str(r.get("products", "") or ""),
                "contract_price": _num(r.get("contract_price"), 0.0),
                "bpc_intrinsic_value_surplus": _num(r.get("bpc_intrinsic_value_surplus"), 0.0),
                "bpc_value_confidence": _num(r.get("v2_value_confidence"), 0.0),
                "bpc_market_sample_count": _num(r.get("bpc_market_sample_count"), 0.0),
                "bpc_discount_vs_median": _num(r.get("bpc_discount_vs_median"), 0.0),
                "date_expired": str(r.get("date_expired", "") or ""),
            }
        )
    return rows


def main() -> None:
    mfg = _read(MFG_SOURCE)
    values = _read(VALUE_SOURCE)

    rows = manufacturing_rows(mfg)
    mfg_contracts = {int(r["contract_id"]) for r in rows}
    rows.extend(intrinsic_rows(values, mfg_contracts))

    stage_rank = {"MAIL": 0, "SAFE": 1, "WATCH": 2, "RESEARCH": 3, "DANGER": 4}
    rows.sort(
        key=lambda r: (
            stage_rank.get(str(r.get("policy_stage", "")), 9),
            -float(r.get("opportunity_score") or 0.0),
            -float(r.get("net_profit") or 0.0),
        )
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)

    mail_count = sum(1 for r in rows if bool(r.get("mail_eligible")))
    watch_count = sum(1 for r in rows if r.get("policy_stage") == "WATCH")
    lines = [
        "# V3 BPC opportunities",
        "",
        f"- Manufacturing rows: {len(mfg)}",
        f"- Intrinsic-value rows: {len(values)}",
        f"- V3 formal MAIL: {mail_count}",
        f"- V3 WATCH: {watch_count}",
        "",
        "BPC formal mail uses exactly four gates: Jita manufacturing net profit >=50M, ROI >=10%,",
        "Jita stress profit >0, and complete material/product order-book depth.",
        "Comparable BPC ask-price signals remain WATCH-only and never become automatic mail without execution proof.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"V3 BPC adapter: rows={len(rows)} mail={mail_count} watch={watch_count}")


if __name__ == "__main__":
    main()
