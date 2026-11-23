"""Read-only V4 private-station market funnel investigation.

No ESI/API calls, reruns, mail state or scanning code changes.
Usage: python -m v4.station_funnel_audit --runs 3
"""
from __future__ import annotations
import argparse
import json
import math
from collections import Counter
from pathlib import Path

from v4.market_depth import STATIONS
FLOOR = 50_000_000
ROI = 0.10
DENSITY = 2000

def finite(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) else None

def gates(proof):
    if proof.get("model_candidate") is True:
        return ["MODEL_PASS_SNAPSHOT_NOT_LIVE"]
    reason = str(proof.get("reason", "UNKNOWN"))
    if reason != "BELOW_GATE_OR_STRESS":
        return [reason]
    profit, roi, density, stress = (
        finite(proof.get(field))
        for field in ("profit", "roi", "density", "stress_profit")
    )
    if any(x is None for x in (profit, roi, density, stress)):
        return ["MISSING_NUMERIC_GATE_PROOF"]
    failures = []
    if profit < FLOOR:
        failures.append("NORMAL_NET_BELOW_50M")
    if roi < ROI:
        failures.append("ROI_BELOW_10_PERCENT")
    if density < DENSITY:
        failures.append("DENSITY_BELOW_2000_PER_M3")
    if stress <= FLOOR:
        failures.append("JITA_BUY_STRESS_NET_NOT_ABOVE_50M")
    return failures or ["REASON_CONFLICT_WITH_NUMERIC_GATES"]

def concise(proof):
    fields = (
        "type_id", "reason", "model_candidate", "quantity", "profit", "roi",
        "density", "stress_profit", "haul_isk", "cost", "cargo_volume_m3",
        "source_vwap_isk_per_unit", "jita_vwap_isk_per_unit",
        "ask_order_ids", "bid_order_ids"
    )
    result = {key: proof.get(key) for key in fields if key in proof}
    result["failed_gates"] = gates(proof)
    for label, key in (("local_sell", "source_top5_sell"),
                       ("jita_buy", "jita_top5_buy")):
        levels = proof.get(key)
        if isinstance(levels, dict):
            result[label + "_price_levels"] = levels.get("group_prices_isk")
    return result

def run_one(folder):
    meta = json.loads((folder / "deep_shadow.json").read_text(encoding="utf-8-sig"))
    result = {
        "run": folder.name,
        "market_execution_basis": meta.get("market_execution_basis"),
        "market_prefilter_basis": meta.get("market_prefilter_basis"),
        "market_potential_pairs_all_stations": meta.get("market_potential_pairs"),
        "structure_health": meta.get("structure_health"),
        "stations": {}
    }
    source_ids = {value: name for name, value in STATIONS.items()}
    census = meta.get("market_station_sell_census") or {}
    for name in STATIONS:
        result["stations"][name] = {
            "census": census.get(name),
            "rejection_reasons": {},
            "failed_gates": {},
            "deep_proofs": 0,
            "model_candidates": [],
            "rejected": []
        }
    reasons = {name: Counter() for name in STATIONS}
    failures = {name: Counter() for name in STATIONS}
    with (folder / "all_proofs.jsonl").open(encoding="utf-8-sig") as f:
        for line in f:
            if not line.strip():
                continue
            p = json.loads(line)
            if p.get("kind") != "market":
                continue
            try:
                source = int(p.get("source_location", p.get("source")))
            except (ValueError, TypeError):
                continue
            name = source_ids.get(source)
            if name is None:
                continue
            target = result["stations"][name]
            target["deep_proofs"] += 1
            reasons[name][str(p.get("reason", "UNKNOWN"))] += 1
            failures[name].update(gates(p))
            entry = concise(p)
            if p.get("model_candidate") is True:
                target["model_candidates"].append(entry)
            else:
                target["rejected"].append(entry)
    for name, target in result["stations"].items():
        target["rejection_reasons"] = dict(reasons[name])
        target["failed_gates"] = dict(failures[name])
        target["rejected"].sort(
            key=lambda p: finite(p.get("profit")) if finite(p.get("profit")) is not None else -1,
            reverse=True
        )
        target["normal_gates_pass_but_stress_fails"] = sum(
            item.get("failed_gates") == ["JITA_BUY_STRESS_NET_NOT_ABOVE_50M"]
            for item in target["rejected"]
        )
    return result

def main():
    parser = argparse.ArgumentParser(description="V4 read-only approved private stations funnel audit")
    parser.add_argument("--data-dir", type=Path, default=Path.home() / "EVE-V4-Data")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path.home() / "Desktop" / "V4-4H-O4T-Forensic.json")
    args = parser.parse_args()
    if not 1 <= args.runs <= 12:
        parser.error("--runs must be 1..12")
    runs_dir = args.data_dir / "runs"
    if not runs_dir.is_dir():
        parser.error("V4 runs not found: " + str(runs_dir))
    folders = []
    for folder in sorted(runs_dir.iterdir()):
        if not folder.is_dir():
            continue
        if not (folder / "deep_shadow.json").is_file() or not (folder / "all_proofs.jsonl").is_file():
            continue
        try:
            manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if manifest.get("status") == "SHADOW_RECORDED":
            folders.append(folder)
    if not folders:
        parser.error("No completed V4 proof runs found")
    report = {
        "audit": "READ_ONLY_LOCAL_NO_NETWORK",
        "policy": {"normal_net_min_isk": FLOOR, "min_roi": ROI,
                   "min_density_isk_per_m3": DENSITY,
                   "stressed_net_strictly_above_isk": FLOOR},
        "runs": [run_one(folder) for folder in folders[-args.runs:]]
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("REPORT", args.output)
    for item in report["runs"]:
        print("RUN", item["run"])
        for name in ("4-H", "O4T", "C-J"):
            s = item["stations"][name]
            print(name, "prefilter", (s["census"] or {}).get("sell_types_optimistic_gate_passed"),
                  "deep", s["deep_proofs"], "model", len(s["model_candidates"]),
                  "failed", json.dumps(s["failed_gates"], ensure_ascii=False))
if __name__ == "__main__":
    main()
