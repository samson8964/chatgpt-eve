from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

LOG_DIR = Path("results/v31/logs")
REPORT_JSON = Path("results/latest/v31_timing.json")
REPORT_MD = Path("results/latest/v31_timing.md")

WAVES = [
    (
        "wave1_bpc",
        [
            ("bpc_manufacturing", "runner_buy_only.py"),
            ("bpc_intrinsic_value", "bpc_contract_benchmark_buy_only.py"),
        ],
    ),
    (
        "wave1_policy",
        [
            ("bpc_policy", "apply_buy_only_bpc_policy.py"),
        ],
    ),
    (
        "wave2_public_contracts",
        [
            ("public_v2", "buy_only_contract_scanner_v2.py"),
            ("public_v3", "opportunity_engine_v3_scanner.py"),
        ],
    ),
    (
        "wave3_four_h",
        [
            ("four_h_contract_v2", "four_h_contract_scanner.py"),
            ("four_h_market_v2", "structure_market_arbitrage.py"),
            ("four_h_reverse_v3", "four_h_reverse_scanner_v3.py"),
        ],
    ),
    (
        "wave4_finalize",
        [
            ("mail_candidate_build", "prepare_mail_candidates.py"),
        ],
    ),
    (
        "wave4_links",
        [
            ("action_links", "add_action_links.py"),
        ],
    ),
]


def _tail(path: Path, lines: int = 80) -> str:
    try:
        rows = path.read_text("utf-8", errors="replace").splitlines()
        return "\n".join(rows[-lines:])
    except Exception as exc:
        return f"<unable to read log: {exc}>"


def run_wave(wave_name: str, tasks: list[tuple[str, str]]) -> dict:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    wave_start = time.perf_counter()
    running = {}
    result = {"wave": wave_name, "tasks": {}}

    print(f"\n=== V3.1 {wave_name}: starting {len(tasks)} task(s) ===", flush=True)
    for task_name, script in tasks:
        log_path = LOG_DIR / f"{task_name}.log"
        fh = log_path.open("w", encoding="utf-8")
        started = time.perf_counter()
        proc = subprocess.Popen(
            [sys.executable, script],
            stdout=fh,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
        )
        running[task_name] = {
            "proc": proc,
            "fh": fh,
            "script": script,
            "log_path": log_path,
            "started": started,
            "finished": None,
        }
        print(f"started {task_name}: pid={proc.pid} script={script}", flush=True)

    unfinished = set(running)
    while unfinished:
        for task_name in list(unfinished):
            rec = running[task_name]
            code = rec["proc"].poll()
            if code is None:
                continue
            rec["finished"] = time.perf_counter()
            rec["returncode"] = int(code)
            rec["fh"].close()
            unfinished.remove(task_name)
            elapsed = rec["finished"] - rec["started"]
            print(f"finished {task_name}: rc={code} elapsed={elapsed:.2f}s", flush=True)
        if unfinished:
            time.sleep(0.25)

    failures = []
    for task_name, rec in running.items():
        elapsed = (rec["finished"] or time.perf_counter()) - rec["started"]
        result["tasks"][task_name] = {
            "script": rec["script"],
            "seconds": round(elapsed, 3),
            "returncode": rec["returncode"],
            "log": str(rec["log_path"]),
        }
        if rec["returncode"] != 0:
            failures.append(task_name)

    result["wall_seconds"] = round(time.perf_counter() - wave_start, 3)
    if failures:
        for task_name in failures:
            print(f"\n--- failure tail: {task_name} ---\n{_tail(running[task_name]['log_path'])}", flush=True)
        raise RuntimeError(f"V3.1 wave {wave_name} failed: {', '.join(failures)}")

    return result


def _csv_stats(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {"rows": 0, "safe": 0, "exists": False}
    try:
        df = pd.read_csv(p)
    except pd.errors.EmptyDataError:
        return {"rows": 0, "safe": 0, "exists": True}
    except Exception as exc:
        return {"rows": 0, "safe": 0, "exists": True, "error": str(exc)}
    safe = 0
    if "execution_status" in df.columns:
        safe = int(df["execution_status"].fillna("").astype(str).str.upper().eq("SAFE").sum())
    elif "v2_status" in df.columns:
        safe = int(df["v2_status"].fillna("").astype(str).str.upper().eq("SAFE").sum())
    return {"rows": int(len(df)), "safe": safe, "exists": True}


def _collect_output_stats() -> dict:
    files = {
        "bpc_manufacturing_v2": "results/latest/ranked_opportunities_v2.csv",
        "bpc_safe_mail": "results/latest/bpc_v2_safe_candidates.csv",
        "bpc_value_v2": "results/latest/bpc_value_opportunities_v2.csv",
        "spot_v2": "results/latest/contract_deals.csv",
        "multi_v2": "results/latest/multi_item_contract_deals.csv",
        "four_h_contract_v2": "results/latest/four_h_contract_bargains.csv",
        "four_h_market_v2": "results/latest/four_h_to_jita_buy.csv",
        "cash_floor_v3": "results/latest/v3_cash_floor.csv",
        "barter_v3": "results/latest/v3_barter.csv",
        "conservative_list_v3": "results/latest/v3_conservative_listing.csv",
        "jita_to_four_h_v3": "results/latest/v3_jita_to_four_h.csv",
    }
    return {name: _csv_stats(path) for name, path in files.items()}


def main() -> None:
    started = time.perf_counter()
    waves = []
    for wave_name, tasks in WAVES:
        waves.append(run_wave(wave_name, tasks))

    total = time.perf_counter() - started
    prefetch = {}
    prefetch_path = Path("results/latest/v31_prefetch.json")
    if prefetch_path.exists():
        try:
            prefetch = json.loads(prefetch_path.read_text("utf-8"))
        except Exception:
            prefetch = {}

    payload = {
        "engine_version": "Opportunity Engine V3.1 speed prototype",
        "production_merged": False,
        "parallel_strategy": [
            "BPC manufacturing + intrinsic benchmark",
            "V2 public contracts + V3 public missed-opportunity scan",
            "4-H contract + 4-H->Jita + Jita->4-H scans",
        ],
        "prefetch": prefetch,
        "waves": waves,
        "scan_wall_seconds": round(total, 3),
        "prefetch_plus_scan_seconds": round(total + float(prefetch.get("total_seconds", 0.0) or 0.0), 3),
        "outputs": _collect_output_stats(),
    }

    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")

    lines = [
        "# Opportunity Engine V3.1 speed trial",
        "",
        f"- Scan wall time: **{payload['scan_wall_seconds']:.1f}s**",
        f"- Prefetch + scan: **{payload['prefetch_plus_scan_seconds']:.1f}s**",
        "- Production merge: **NO**",
        "",
        "## Waves",
        "",
        "| Wave | Wall seconds | Tasks |",
        "|---|---:|---|",
    ]
    for wave in waves:
        task_text = ", ".join(
            f"{name}={meta['seconds']:.1f}s"
            for name, meta in wave["tasks"].items()
        )
        lines.append(f"| {wave['wave']} | {wave['wall_seconds']:.1f} | {task_text} |")

    lines += [
        "",
        "## Output counts",
        "",
        "| Channel | Rows | SAFE |",
        "|---|---:|---:|",
    ]
    for name, stats in payload["outputs"].items():
        lines.append(f"| {name} | {stats.get('rows', 0)} | {stats.get('safe', 0)} |")

    REPORT_MD.write_text("\n".join(lines) + "\n", "utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
