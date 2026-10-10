from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone, timedelta
import json

import pandas as pd

LATEST = Path("results/latest")
OUT = LATEST / "v3_cutover_summary.md"

CHANNELS = [
    ("Public FULL_CASH", "v3_full_cash.csv"),
    ("Public PARTIAL_CASH_FLOOR", "v3_cash_floor.csv"),
    ("Public BARTER", "v3_barter.csv"),
    ("Public LIST-SUPPORTED", "v3_conservative_listing.csv"),
    ("Amarr -> Jita", "v3_amarr_to_jita.csv"),
    ("Dodixie -> Jita", "v3_dodixie_to_jita.csv"),
    ("4-H market -> Jita", "v3_four_h_to_jita.csv"),
    ("C-J market -> Jita", "v3_cj_to_jita.csv"),
    ("4-H contracts", "v3_four_h_contracts.csv"),
    ("C-J contracts", "v3_cj_contracts.csv"),
    ("Jita -> 4-H", "v3_jita_to_four_h.csv"),
    ("BPC manufacturing/value", "v3_bpc_opportunities.csv"),
]


def read(name: str) -> pd.DataFrame:
    path = LATEST / name
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def truthy(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(str).str.lower().isin({"1", "true", "t", "yes", "y"})


def main() -> None:
    LATEST.mkdir(parents=True, exist_ok=True)
    lines = [
        "# V3 production summary",
        "",
        "V3 is the production opportunity engine. Legacy V2 public/structure production scanners are disabled.",
        "Amarr and Dodixie are procurement sources only; all exit valuation remains Jita 4-4 BUY depth.",
        "",
        "| Channel | Scan health | Rows | MAIL | SAFE | WATCH | RESEARCH | Best net profit |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    health_file = LATEST / "v3_scan_health.json"
    try:
        health = json.loads(health_file.read_text(encoding="utf-8")) if health_file.exists() else {}
    except (OSError, ValueError):
        health = {}
    health_by_channel = health.get("channels", {})
    total_mail = 0
    bpc_historical_count = 0
    for label, name in CHANNELS:
        key = name.removesuffix(".csv").replace("_", "-").replace("v3-jita-to-four-h", "v3-jita-to-4h")
        status = health_by_channel.get(key, {}).get("status", "-")
        df = read(name)
        if name == "v3_bpc_opportunities.csv" and not df.empty:
            # Fast scans retain previous deep-BPC files. Historical verified
            # opportunities must never inflate the live formal MAIL summary.
            verified = pd.to_datetime(df.get("verified_at", pd.Series(index=df.index, dtype="object")), utc=True, errors="coerce")
            now = datetime.now(timezone.utc)
            fresh = verified.between(now - timedelta(hours=6), now + timedelta(minutes=2))
            bpc_historical_count = int((~fresh).sum())
            df = df.loc[fresh].copy()
            status = "fresh" if not df.empty else "stale"
        if df.empty:
            lines.append(f"| {label} | {status} | 0 | 0 | 0 | 0 | 0 | - |")
            continue
        stage = df.get("policy_stage")
        if stage is None:
            stage = df.get("execution_status", pd.Series([""] * len(df)))
        stage = stage.fillna("").astype(str).str.upper()
        if "mail_eligible" in df.columns:
            mail = int(truthy(df["mail_eligible"]).sum())
        else:
            mail = int((stage == "MAIL").sum())
        total_mail += mail
        safe = int(stage.isin({"SAFE", "MAIL"}).sum())
        watch = int((stage == "WATCH").sum())
        research = int((stage == "RESEARCH").sum())
        profit = pd.to_numeric(df.get("net_profit"), errors="coerce")
        best = float(profit.max()) if profit is not None and profit.notna().any() else float("nan")
        best_text = f"{best/1e6:.1f}M" if pd.notna(best) else "-"
        lines.append(f"| {label} | {status} | {len(df)} | {mail} | {safe} | {watch} | {research} | {best_text} |")

    lines += [
        "",
        f"- Total currently verified formal MAIL decisions across V3 outputs: **{total_mail}**",
        "- Formal MAIL decisions are eligible for the unified V3 in-game mail sender.",
        "- Market scan health: ok = fresh nonempty, empty = completed with no rows; failed/missing_output/invalid_output must not trigger mail.",
        f"- Historical/unverified BPC rows excluded from live counts: {bpc_historical_count}.",
        "- BPC live count excludes manufacturing rows whose live verification is older than six hours or missing; historical BPC CSV can still exist.",
    ]
    OUT.write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
