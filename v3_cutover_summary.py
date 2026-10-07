from __future__ import annotations

from pathlib import Path

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
        "# V3 cutover test summary",
        "",
        "Production V2 public/structure scanners are not part of this test run.",
        "Amarr and Dodixie are procurement sources only; all exit valuation remains Jita 4-4 BUY depth.",
        "",
        "| Channel | Rows | MAIL | SAFE | WATCH | RESEARCH | Best net profit |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    total_mail = 0
    for label, name in CHANNELS:
        df = read(name)
        if df.empty:
            lines.append(f"| {label} | 0 | 0 | 0 | 0 | 0 | - |")
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
        lines.append(f"| {label} | {len(df)} | {mail} | {safe} | {watch} | {research} | {best_text} |")

    lines += [
        "",
        f"- Total formal MAIL decisions across V3 test outputs: **{total_mail}**",
        "- V3 mail delivery is intentionally disabled during this cutover test; decisions are recorded only.",
    ]
    OUT.write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
