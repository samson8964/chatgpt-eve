from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(os.getenv("EVE_V31_RUN_ROOT", ".run/v31")).resolve()
LOG_DIR = ROOT / "logs"
METRICS_PATH = ROOT / "stage_metrics.json"


def _env(patch: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    if patch:
        env.update({k: str(v) for k, v in patch.items()})
    return env


def run_cmd(label: str, cmd: list[str], patch: dict[str, str] | None = None) -> dict:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"{label}.log"
    started = time.monotonic()
    with path.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(
            cmd,
            env=_env(patch),
            stdout=fh,
            stderr=subprocess.STDOUT,
            text=True,
        )
    elapsed = time.monotonic() - started
    result = {
        "label": label,
        "cmd": cmd,
        "returncode": proc.returncode,
        "seconds": round(elapsed, 3),
        "log": str(path),
    }
    print(f"[{label}] returncode={proc.returncode} elapsed={elapsed:.1f}s")
    if proc.returncode != 0:
        tail = path.read_text("utf-8", errors="replace")[-5000:]
        print(f"--- {label} tail ---\n{tail}\n--- end {label} ---")
        raise RuntimeError(f"V3.1 lane step failed: {label}")
    return result


def run_lane(name: str, steps: list[tuple[str, list[str], dict[str, str]]]) -> dict:
    started = time.monotonic()
    results = []
    for label, cmd, patch in steps:
        results.append(run_cmd(label, cmd, patch))
    return {
        "lane": name,
        "seconds": round(time.monotonic() - started, 3),
        "steps": results,
    }


def main() -> None:
    if not os.getenv("EVE_RUN_SNAPSHOT_MANIFEST"):
        raise RuntimeError("V3.1 shared snapshot manifest is missing; run v31_prepare_shared.py first")
    if not os.getenv("EVE_RUN_4H_ORDERS_PATH"):
        raise RuntimeError("V3.1 shared 4-H snapshot is missing; run v31_prepare_shared.py first")
    if not os.getenv("EVE_RUN_CACHE_DIR"):
        raise RuntimeError("V3.1 run cache is missing")

    py = sys.executable
    started = time.monotonic()

    lanes = {
        "bpc_manufacturing": [
            (
                "bpc_manufacturing",
                [py, "runner_buy_only.py"],
                {
                    "MARKET_BROKER_FEE_RATE": "0",
                    "EXPECTED_RELISTS": "0",
                    "DEAL_MAX_CONTRACT_PRICE": "5000000000",
                    "PREFILTER_TOP": "500",
                },
            )
        ],
        "bpc_intrinsic": [
            (
                "bpc_intrinsic",
                [py, "bpc_contract_benchmark_buy_only.py"],
                {
                    "BPC_VALUE_MIN_SAMPLES": "3",
                    "BPC_VALUE_MIN_EXACT_SAMPLES": "3",
                    "BPC_VALUE_MIN_DISCOUNT": "0.25",
                    "BPC_VALUE_MIN_MEDIAN_DISCOUNT": "0.10",
                    "BPC_VALUE_MIN_SURPLUS": "10000000",
                    "BPC_VALUE_MIN_HOURS_TO_EXPIRE": "2",
                    "BPC_VALUE_TOP": "200",
                    "DEAL_MAX_CONTRACT_PRICE": "5000000000",
                    "DEAL_FRIENDLY_CHARACTER_ID": "2124493042",
                    "DEAL_FRIENDLY_ALLIANCE_IDS": "",
                    "DEAL_FRIENDLY_REGION_IDS": "",
                },
            )
        ],
        "v2_public": [
            (
                "v2_public",
                [py, "buy_only_contract_scanner_v2.py"],
                {
                    "DEAL_MIN_CONTRACT_PRICE": "1000000",
                    "DEAL_MAX_CONTRACT_PRICE": "5000000000",
                    "DEAL_MIN_NET_PROFIT": "30000000",
                    "DEAL_MIN_NET_ROI": "0.10",
                    "DEAL_MIN_HOURS_TO_EXPIRE": "0.5",
                    "DEAL_TOP": "250",
                    "MULTI_TOP": "250",
                    "DEAL_SKIN_MAJOR_SHARE": "0.50",
                    "DEAL_HAUL_BASE_ISK": "2000000",
                    "DEAL_HAUL_ISK_PER_M3_JUMP": "200",
                    "DEAL_FRIENDLY_CHARACTER_ID": "2124493042",
                    "DEAL_FRIENDLY_ALLIANCE_IDS": "",
                    "DEAL_FRIENDLY_REGION_IDS": "",
                    "V2_LIVE_REVALIDATE_LIMIT": "120",
                    "V2_HISTORY_CANDIDATE_LIMIT": "60",
                    "V2_LIVE_WORKERS": "8",
                    "V2_HISTORY_WORKERS": "8",
                },
            )
        ],
        "four_h_contract": [
            (
                "four_h_contract",
                [py, "four_h_contract_scanner.py"],
                {
                    "FOUR_H_STRUCTURE_ID": "1053970513596",
                    "FOUR_H_CONTRACT_MIN_PRICE": "1000000",
                    "FOUR_H_CONTRACT_MIN_NET_PROFIT": "5000000",
                    "FOUR_H_CONTRACT_MIN_NET_ROI": "0.05",
                    "FOUR_H_CONTRACT_TOP": "100",
                    "ACCOUNTING_LEVEL": "5",
                },
            )
        ],
        "four_h_market": [
            (
                "four_h_market",
                [py, "structure_market_arbitrage.py"],
                {
                    "FOUR_H_STRUCTURE_ID": "1053970513596",
                    "FOUR_H_MIN_NET_PROFIT": "10000000",
                    "FOUR_H_MIN_NET_ROI": "0.10",
                    "FOUR_H_TOP": "100",
                    "ACCOUNTING_LEVEL": "5",
                    "V2_FOUR_H_MARKET_LIVE_LIMIT": "150",
                    "V2_FOUR_H_MARKET_HISTORY_LIMIT": "80",
                    "V2_LIVE_WORKERS": "8",
                    "V2_HISTORY_WORKERS": "8",
                },
            )
        ],
        "v3_public": [
            (
                "v3_public",
                [py, "opportunity_engine_v3_scanner.py"],
                {
                    "DEAL_MIN_CONTRACT_PRICE": "1000000",
                    "DEAL_MAX_CONTRACT_PRICE": "5000000000",
                    "DEAL_MIN_HOURS_TO_EXPIRE": "0.5",
                    "DEAL_SKIN_MAJOR_SHARE": "0.50",
                    "DEAL_HAUL_BASE_ISK": "2000000",
                    "DEAL_HAUL_ISK_PER_M3_JUMP": "200",
                    "DEAL_FRIENDLY_CHARACTER_ID": "2124493042",
                    "DEAL_FRIENDLY_ALLIANCE_IDS": "",
                    "DEAL_FRIENDLY_REGION_IDS": "",
                    "V3_PUBLIC_LIVE_LIMIT": "300",
                    "V3_PUBLIC_PER_METRIC": "110",
                    "V3_PUBLIC_NEWEST_COUNT": "60",
                    "V3_LIST_HISTORY_LIMIT": "120",
                    "V3_LIVE_WORKERS": "8",
                },
            )
        ],
        "v3_reverse": [
            (
                "v3_reverse",
                [py, "four_h_reverse_scanner_v3.py"],
                {
                    "FOUR_H_STRUCTURE_ID": "1053970513596",
                    "V3_4H_REVERSE_MIN_PROFIT": "20000000",
                    "V3_4H_REVERSE_MIN_ROI": "0.10",
                    "V3_4H_REVERSE_HAUL_BASE": "10000000",
                    "V3_4H_REVERSE_HAUL_ISK_PER_M3": "500",
                    "V3_LIVE_WORKERS": "8",
                },
            )
        ],
    }

    lane_results = {}
    errors = []
    print(f"V3.1 starting {len(lanes)} parallel lanes")
    with ThreadPoolExecutor(max_workers=len(lanes)) as ex:
        futs = {ex.submit(run_lane, name, steps): name for name, steps in lanes.items()}
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                lane_results[name] = fut.result()
            except Exception as exc:
                errors.append((name, repr(exc)))

    metrics = {
        "version": "3.1-experimental",
        "parallel_seconds": round(time.monotonic() - started, 3),
        "lanes": lane_results,
        "errors": errors,
    }
    ROOT.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), "utf-8")

    if errors:
        raise RuntimeError(f"V3.1 parallel lanes failed: {errors}")

    # Unified post-processing starts only after every scanner has finished, so mail
    # candidates cannot see a half-updated mixture of V2/V3/4-H outputs.
    post_started = time.monotonic()
    post = []
    # BPC policy depends on both BPC discovery products, so it runs once after the
    # manufacturing and intrinsic lanes have completed. Keeping it out of either lane
    # removes an unnecessary 90s+ serialization from the critical path.
    post.append(
        run_cmd(
            "bpc_policy",
            [py, "apply_buy_only_bpc_policy.py"],
            {"DEAL_MAX_CONTRACT_PRICE": "5000000000"},
        )
    )
    post.append(
        run_cmd(
            "prepare_mail_candidates",
            [py, "prepare_mail_candidates.py"],
            {
                "MAIL_SPOT_MIN_PROFIT": "30000000",
                "MAIL_SPOT_MIN_ROI": "0.10",
                "MAIL_BPC_VALUE_MIN_SAMPLES": "5",
                "MAIL_BPC_VALUE_MIN_AVG_DISCOUNT": "0.30",
                "MAIL_BPC_VALUE_MIN_MEDIAN_DISCOUNT": "0.20",
                "MAIL_BPC_VALUE_MIN_SURPLUS": "20000000",
                "MAIL_BPC_MFG_MIN_PROFIT": "20000000",
                "MAIL_BPC_MFG_MIN_ROI": "0.10",
                "BPC_V2_LIVE_WORKERS": "8",
            },
        )
    )
    post.append(run_cmd("add_action_links", [py, "add_action_links.py"], {}))

    metrics["post_steps"] = post
    metrics["post_seconds"] = round(time.monotonic() - post_started, 3)
    metrics["total_scan_seconds"] = round(time.monotonic() - started, 3)
    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), "utf-8")

    # v31_finalize verifies immutable inputs, reports cache effectiveness, produces a
    # unified summary, and optionally sends all existing mail channels in one final phase.
    run_cmd("v31_finalize", [py, "v31_finalize.py"], {})
    metrics["total_with_finalize_seconds"] = round(time.monotonic() - started, 3)
    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), "utf-8")
    print(f"V3.1 complete in {metrics['total_with_finalize_seconds']:.1f}s")


if __name__ == "__main__":
    main()
