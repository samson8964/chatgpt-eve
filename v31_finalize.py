from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

from run_cache_v31 import stats as cache_stats

LATEST = Path("results/latest")

CHANNELS = [
    ("v2_spot", LATEST / "contract_deals.csv", "execution_status", "net_profit"),
    ("v2_multi", LATEST / "multi_item_contract_deals.csv", "execution_status", "net_profit"),
    ("v2_bpc_mfg", LATEST / "bpc_v2_safe_candidates.csv", "v2_status", "v2_live_net_profit"),
    ("v2_four_h_contract", LATEST / "four_h_contract_bargains.csv", "execution_status", "best_net_profit"),
    ("v2_four_h_market", LATEST / "four_h_to_jita_buy.csv", "execution_status", "net_profit"),
    ("v3_cash_floor", LATEST / "v3_cash_floor.csv", "execution_status", "net_profit"),
    ("v3_barter", LATEST / "v3_barter.csv", "execution_status", "net_profit"),
    ("v3_conservative_list", LATEST / "v3_conservative_listing.csv", "execution_status", "net_profit"),
    ("v3_jita_to_4h", LATEST / "v3_jita_to_four_h.csv", "execution_status", "net_profit"),
]

MAIL_COMMANDS = [
    ("core", [sys.executable, "send_eve_mail_buy_only_multi.py"], {}),
    ("multi", [sys.executable, "send_multi_item_buy_only_multi.py"], {}),
    ("four_h", [sys.executable, "send_four_h_mail_multi.py"], {}),
    (
        "v3_public",
        [sys.executable, "send_v3_opportunity_mail.py"],
        {"V3_CHANNELS": "v3-cash-floor,v3-barter,v3-conservative-list"},
    ),
    (
        "v3_reverse",
        [sys.executable, "send_v3_opportunity_mail.py"],
        {"V3_CHANNELS": "v3-jita-to-4h"},
    ),
]


def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_shared_inputs() -> dict:
    manifest_path = Path(os.environ["EVE_RUN_SNAPSHOT_MANIFEST"])
    manifest = json.loads(manifest_path.read_text("utf-8"))
    checks = {}
    for key, entry in (manifest.get("datasets") or {}).items():
        path = Path(entry["path"])
        actual = _hash(path)
        expected = str(entry.get("sha256") or "")
        ok = actual == expected
        checks[key] = {"ok": ok, "sha256": actual, "expected": expected, "path": str(path)}
        if not ok:
            raise RuntimeError(f"Shared snapshot mutated during run: {key}")
    return checks


def summarize_channels() -> dict:
    out = {}
    for name, path, status_col, profit_col in CHANNELS:
        df = _read(path)
        if df.empty:
            out[name] = {"rows": 0, "safe": 0, "top_profit": 0.0}
            continue
        if status_col in df.columns:
            safe_mask = df[status_col].fillna("").astype(str).str.upper().eq("SAFE")
            safe_count = int(safe_mask.sum())
        else:
            safe_count = len(df)
        profit = pd.to_numeric(df.get(profit_col), errors="coerce") if profit_col in df.columns else pd.Series(dtype=float)
        out[name] = {
            "rows": int(len(df)),
            "safe": safe_count,
            "top_profit": float(profit.max()) if not profit.empty and profit.notna().any() else 0.0,
        }
    return out


def run_mail_once() -> dict:
    enabled = os.getenv("V31_SEND_MAIL", "0").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        return {"enabled": False, "outcomes": {}}

    required = {
        "EVE_MAIL_API_KEY": os.getenv("EVE_MAIL_API_KEY", "").strip(),
        "EVE_MAIL_WORKER_URL": os.getenv("EVE_MAIL_WORKER_URL", "").strip(),
        "EVE_MAIL_RECIPIENT_NAMES": os.getenv("EVE_MAIL_RECIPIENT_NAMES", "").strip(),
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"V3.1 mail preflight missing environment: {', '.join(missing)}")

    outcomes = {}
    for name, cmd, patch in MAIL_COMMANDS:
        env = os.environ.copy()
        env.update(patch)
        started = time.monotonic()
        proc = subprocess.run(cmd, env=env, text=True, capture_output=True)
        outcomes[name] = {
            "returncode": proc.returncode,
            "seconds": round(time.monotonic() - started, 3),
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-2000:],
        }
        if proc.returncode != 0:
            raise RuntimeError(f"Unified V3.1 mail stage failed: {name}")
    return {"enabled": True, "outcomes": outcomes}


def main() -> None:
    root = Path(os.getenv("EVE_V31_RUN_ROOT", ".run/v31")).resolve()
    metrics_path = root / "stage_metrics.json"
    stage_metrics = json.loads(metrics_path.read_text("utf-8")) if metrics_path.exists() else {}

    input_checks = verify_shared_inputs()
    channels = summarize_channels()
    cache = cache_stats()
    mail = run_mail_once()

    summary = {
        "version": "3.1-experimental",
        "created_at_epoch": time.time(),
        "stage_metrics": stage_metrics,
        "shared_inputs": input_checks,
        "cache": cache,
        "channels": channels,
        "mail": mail,
    }
    out_json = LATEST / "v31_run_summary.json"
    out_md = LATEST / "v31_run_summary.md"
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")

    lines = [
        "# Opportunity Engine V3.1 experimental run",
        "",
        "## Shared inputs",
    ]
    for key, check in input_checks.items():
        lines.append(f"- {key}: immutable={check['ok']}")
    lines += ["", "## Channels"]
    for name, row in channels.items():
        lines.append(
            f"- {name}: rows={row['rows']} SAFE={row['safe']} top_profit={row['top_profit']:,.0f}"
        )
    lines += [
        "",
        "## Run cache",
        f"- requests={cache.get('requests', 0)}",
        f"- hits={cache.get('hits', 0)}",
        f"- misses={cache.get('misses', 0)}",
        f"- writes={cache.get('writes', 0)}",
        f"- lock_wait_seconds={cache.get('lock_wait_seconds', 0)}",
        "",
        f"Mail enabled: {mail.get('enabled', False)}",
    ]
    out_md.write_text("\n".join(lines) + "\n", "utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
