"""Read-only V4 contract/blueprint funnel diagnostic for completed local runs.

No network, secrets, ESI calls, orders, mail, or DB mutations. Report only
aggregates from existing full_market_report.json, deep_shadow.json and
all_proofs.jsonl. Distinguish missing manufacturing proofs from zero profit.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("INVALID_JSON_OBJECT")
    return value


def _finite(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _top(counts: Counter, limit: int = 12) -> dict:
    return dict(counts.most_common(limit))


def _gate(row: dict) -> bool:
    n = _finite(row.get("net_profit"))
    r = _finite(row.get("roi"))
    return n is not None and n >= 50_000_000 and r is not None and r > 0.10


def inspect_run(folder: Path, *, repo: Path | None = None) -> dict:
    """Never run a scan; open completed read-only snapshots only."""
    folder = Path(folder)
    manifest = _json(folder / "manifest.json")
    if manifest.get("status") != "SHADOW_RECORDED":
        raise ValueError("RUN_NOT_COMPLETED")
    deep = _json(folder / "deep_shadow.json")
    census = _json(folder / "full_market_report.json")
    if deep.get("status") != "SHADOW_ONLY_NO_LIVE_ALERTS":
        raise ValueError("NOT_A_SHADOW_AUDIT")

    counts = Counter()
    reasons = {"contract": Counter(), "blueprint_manufacturing": Counter()}
    candidate = Counter()
    numeric_gate = Counter()
    contract_no_bid = contract_bp_ignored = contract_unclassified = 0
    contract_net_roi_below_market_density = 0
    contract_net_roi_with_unknown_volume = 0
    blueprint_types = set()
    proof_count = 0
    with (folder / "all_proofs.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("INVALID_PROOF_JSON")
            proof_count += 1
            kind = str(row.get("kind") or "unknown")
            counts[kind] += 1
            if row.get("model_candidate") is True:
                candidate[kind] += 1
            if kind in reasons:
                reasons[kind][str(row.get("reason") or "UNSPECIFIED")] += 1
                if _gate(row):
                    numeric_gate[kind] += 1
            if kind == "contract":
                # This is a diagnostic COMPARISON with the market Policy()
                # density setting, not a claim that contracts are already
                # contract-policy density-gated in production.
                if _gate(row):
                    net = _finite(row.get("net_profit"))
                    volume = _finite(row.get("cargo_volume_m3"))
                    if volume is None or volume <= 0:
                        contract_net_roi_with_unknown_volume += 1
                    elif net / volume < 2_000:
                        contract_net_roi_below_market_density += 1
                contract_no_bid += int(row.get("ignored_no_bid_types") or 0)
                contract_bp_ignored += int(row.get("ignored_blueprint_types") or 0)
                contract_unclassified += int(
                    row.get("ignored_unclassified_types") or 0)
            if kind == "blueprint_manufacturing":
                typ = row.get("blueprint_type_id")
                if isinstance(typ, int) and not isinstance(typ, bool):
                    blueprint_types.add(typ)

    expected = deep.get("proof_count")
    if type(expected) is int and expected != proof_count:
        raise ValueError("PROOF_COUNT_MISMATCH")
    contracted = census.get("contracts") or {}
    return {
        "status": "READ_ONLY_FUNNEL_REPORTED",
        "run": folder.name,
        "run_finished_at": manifest.get("finished_at"),
        "coverage_gate": manifest.get("coverage_gate"),
        "structure_status": {k:(v or {}).get("status") for k,v
                             in (deep.get("structure_health") or {}).items()},
        "public_contract_ingestion": {
            "archive_contracts": contracted.get("contract_rows_total"),
            "archive_contract_item_rows": contracted.get("contract_item_rows_total"),
            "cash_item_exchange_approved_locations": deep.get(
                "contract_cash_known_location"),
            "barter_requested_items_excluded": deep.get(
                "contract_requested_items_excluded"),
            "jita_cash_contracts": deep.get("contract_jita_examined"),
            "approved_cash_contracts": deep.get(
                "contract_approved_locations_examined"),
            "npc_catalog_status": deep.get("npc_catalog_status"),
        },
        "proofs": {
            "total": proof_count,
            "by_kind": dict(counts),
            "contract_model_candidates": candidate["contract"],
            "contract_numeric_gate_before_mail_exclusions":
                numeric_gate["contract"],
            "contract_rejection_reasons": _top(reasons["contract"], 18),
            "contract_numeric_gate_but_below_2000_isk_per_m3_market_reference":
                contract_net_roi_below_market_density,
            "contract_numeric_gate_with_unknown_cargo_volume":
                contract_net_roi_with_unknown_volume,
            "blueprint_manufacturing_proofs_generated":
                counts["blueprint_manufacturing"],
            "blueprint_manufacturing_model_candidates":
                candidate["blueprint_manufacturing"],
            "blueprint_numeric_gate_before_mail_exclusions":
                numeric_gate["blueprint_manufacturing"],
            "blueprint_rejection_reasons":
                _top(reasons["blueprint_manufacturing"], 12),
            "distinct_blueprint_type_ids_in_manufacturing_proofs":
                len(blueprint_types),
        },
        "blueprint_reference": {
            "recipe_status_at_scan": deep.get(
                "blueprint_manufacturing_recipe_status"),
            "recipe_count_at_scan": deep.get(
                "blueprint_manufacturing_recipe_count"),
            "recipe_error_type_at_scan": deep.get(
                "blueprint_manufacturing_recipe_error_type"),
            "valuation_errors": deep.get(
                "blueprint_manufacturing_valuation_errors"),
            "bpc_bpo_unknown_instances": deep.get("contract_blueprint_states"),
            "ordinary_contract_blueprint_type_credits_ignored":
                contract_bp_ignored,
            "ordinary_contract_types_without_jita_buy_depth":
                contract_no_bid,
            "ordinary_contract_unclassified_types":
                contract_unclassified,
        },
        "interpretation_limits": [
            "Archive count is all public contracts; approved item exchanges are narrower.",
            "BPC/BPO counts are item quantities, not necessarily contract counts.",
            "Blueprint manufacturing proofs count only evaluable jobs; missing recipe, "
            "unknown runs/ME, missing Jita input/output liquidity and unknown hauling "
            "may produce NO manufacturing proof at all.",
            "The 2000 ISK/m3 diagnostic is a comparison to the current market Policy;"
            " ordinary cash contracts do NOT currently enforce that density floor.",
            "Mail additionally excludes capital/freighter types and caps each category "
            "at 10 by first discovery. This audit does not send or re-rank mail.",
            "No proof here verifies current live trade availability.",
        ],
        "local_files_modified": False,
        "mail_sent": False,
        "market_scan_started": False,
    }


def latest_folders(root: Path, last: int = 1) -> list[Path]:
    scans = Path(root) / "runs"
    selected = []
    if not scans.is_dir():
        raise ValueError("RUNS_DIRECTORY_NOT_FOUND")
    for folder in sorted(scans.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        path = folder / "manifest.json"
        if not path.is_file():
            continue
        try:
            if _json(path).get("status") == "SHADOW_RECORDED":
                selected.append(folder)
        except (OSError, ValueError):
            continue
        if len(selected) == last:
            break
    if not selected:
        raise ValueError("NO_COMPLETED_RUNS")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path,
                        default=Path.home() / "EVE-V4-Data")
    parser.add_argument("--last", type=int, default=3,
                        help="Number of most recent completed runs (default 3, max 20)")
    opts = parser.parse_args()
    if opts.last < 1 or opts.last > 20:
        parser.error("--last must be between 1 and 20")
    try:
        reports = [inspect_run(p) for p in latest_folders(opts.data_root, opts.last)]
        print(json.dumps({"status":"READ_ONLY_DIAGNOSTICS_COMPLETE",
                          "runs":reports, "files_modified":False},
                         ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status":"READ_ONLY_DIAGNOSTICS_FAILED",
                          "error_type":type(exc).__name__,
                          "error":str(exc)[:150], "files_modified":False},
                         ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
