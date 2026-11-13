"""Read-only V4 historical scan-funnel and coverage accounting audit.

Reads saved V4 reports; does not access ESI, send mail, update the SQLite
database, change the scheduler or infer that upstream EVE Ref was complete.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

LANES = (("four_h", "4-H"), ("cj", "C-J"), ("o4t", "O4T"))


def _read(path: Path) -> dict:
    item = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(item, dict):
        raise ValueError("V4_REPORT_NOT_AN_OBJECT")
    return item


def _int(obj: dict, key: str):
    value = obj.get(key)
    return int(value) if value is not None else None


def _equal(a, b):
    return None if a is None or b is None else a == b


def audit_run(folder: Path) -> dict:
    manifest = _read(folder / "manifest.json")
    full = _read(folder / "full_market_report.json")
    deep = _read(folder / "deep_shadow.json")
    if manifest.get("status") != "SHADOW_RECORDED":
        raise ValueError("NOT_A_COMPLETED_SHADOW_RUN")

    market, contracts = full.get("market") or {}, full.get("contracts") or {}
    lanes = deep.get("structure_health") or {}
    stations = deep.get("market_station_sell_census") or {}
    report = {
        "run": folder.name,
        "started_at_utc": manifest.get("started_at"),
        "finished_at_utc": manifest.get("finished_at"),
        "data_gate": manifest.get("coverage_gate"),
        "source_input_integrity": deep.get("source_input_integrity"),
        "full_census_status": full.get("overall"),
        "public_market_raw_order_rows": _int(market, "market_raw_rows"),
        "public_market_active_orders_parsed": _int(deep, "public_market_orders"),
        "public_market_sell_order_rows": _int(market, "sell_order_rows"),
        "public_market_buy_order_rows": _int(market, "buy_order_rows"),
        "public_market_locations": _int(market, "market_locations"),
        "public_market_types": _int(market, "market_types"),
        "public_market_sell_station_item_pairs": _int(market, "source_location_type_pairs"),
        "public_market_global_best_bid_optimistic_pairs": _int(market, "optimistic_initial_candidates"),
        "authorized_structures_active_orders": _int(deep, "authorized_structure_orders"),
        "market_approved_locations_including_jita": _int(deep, "verified_approved_locations"),
        "market_jita_exit_gross_gate_pairs": _int(deep, "market_potential_pairs"),
        "market_deep_proofs_examined": _int(deep, "market_proofs_examined"),
        "all_public_contracts": _int(contracts, "contract_rows_total"),
        "all_public_contract_item_rows": _int(contracts, "contract_item_rows_total"),
        "contract_source_and_cash_exchange_approved": _int(deep, "contract_approved_locations_examined"),
        "npc_contracts_in_approved_scope": _int(deep, "npc_contracts_approved_for_deep_analysis"),
        "stations": {},
        "quality_checks": {},
        "evidence_limits": [
            "Upstream EVE Ref index metadata and file parsing do not prove every ESI page or region was collected.",
            "Global market precheck is optimistic with ANY-region top bid; deep market trading proofs use approved source locations and Jita 4-4 bids only.",
            "Not every captured order reaches a deep profit proof: non-crossed books and pairs below 50m gross bound are excluded on purpose.",
            "Contract location qualification does not mean every contract passed item checks, buy-depth, haul, ROI and mail gates.",
            "No snapshot report verifies real-time prices or contract availability."
        ],
    }
    checks = report["quality_checks"]
    checks["all_parsed_without_invalid_orders"] = (
        deep.get("source_input_integrity") == "ALL_PARSED")
    sources = full.get("sources") or {}
    checks["both_eve_ref_archives_downloaded"] = all(
        (sources.get(name) or {}).get("status") == "COMPLETE"
        for name in ("market_orders", "public_contracts")
    ) if sources else None
    public_raw = _int(deep, "public_market_rows_raw")
    public_active = _int(deep, "public_market_orders")
    public_zero = _int(deep, "zero_remaining_public_orders")
    public_invalid = _int(deep, "invalid_public_orders")
    checks["public_census_same_as_deep_raw"] = _equal(
        _int(market, "market_raw_rows"), public_raw)
    checks["public_order_accounting_exact"] = (
        _equal(public_raw, public_active + public_zero + public_invalid)
        if None not in (public_active, public_zero, public_invalid) else None
    )
    structure_raw = _int(deep, "structure_market_rows_raw")
    structure_active = _int(deep, "authorized_structure_orders")
    structure_zero = _int(deep, "zero_remaining_structure_orders")
    structure_invalid = _int(deep, "invalid_structure_orders")
    checks["structure_order_accounting_exact"] = (
        _equal(structure_raw, structure_active + structure_zero + structure_invalid)
        if None not in (structure_active, structure_zero, structure_invalid) else None
    )
    raw_by_lane = []
    for key, label in LANES:
        lane = lanes.get(key) or {}
        census = stations.get(label) or {}
        n = _int(lane, "orders")
        if n is not None:
            raw_by_lane.append(n)
        pages = _int(lane, "pages")
        fetched = _int(lane, "pages_fetched")
        report["stations"][label] = {
            "status": lane.get("status", "MISSING"),
            "raw_orders": n,
            "pages_expected": pages,
            "pages_fetched": fetched,
            "active_sell_orders": _int(census, "active_sell_orders"),
            "active_buy_orders": _int(census, "active_buy_orders"),
            "sell_item_types": _int(census, "active_sell_type_ids"),
            "sell_types_with_jita_buy": _int(census, "sell_types_with_jita_buy"),
            "sell_types_without_jita_buy": _int(census, "sell_types_without_jita_buy"),
            "sell_types_crossed_jita_best_buy": _int(census, "sell_types_best_price_crossed"),
            "sell_types_gross_margin_at_least_50m": _int(census, "sell_types_optimistic_gate_passed"),
            "pages_complete": lane.get("status") == "COMPLETE" and pages is not None
                              and pages > 0 and fetched == pages,
        }
    checks["all_three_structure_page_ranges_complete"] = all(
        report["stations"][label]["pages_complete"] for _, label in LANES)
    checks["structure_raw_equals_lane_sum"] = (
        _equal(structure_raw, sum(raw_by_lane)) if len(raw_by_lane) == len(LANES) else None
    )
    checks["market_gross_gate_to_deep_proof_count_exact"] = _equal(
        _int(deep, "market_potential_pairs"), _int(deep, "market_proofs_examined"))
    checks["census_finished"] = full.get("overall") == "CENSUS_COMPLETE_PROOFS_NOT_READY"
    report["local_book_coverage_checks_pass"] = (
        all(v is True for v in checks.values()))
    return report


def history(root: Path, *, last: int = 10) -> dict:
    runs = root / "runs"
    if not runs.is_dir():
        raise FileNotFoundError("V4_RUNS_DIRECTORY_NOT_FOUND")
    if last < 1 or last > 200:
        raise ValueError("INVALID_HISTORY_COUNT")
    out = []
    for folder in sorted((f for f in runs.iterdir() if f.is_dir()),
                         key=lambda f: f.name, reverse=True):
        try:
            manifest = _read(folder / "manifest.json")
        except (FileNotFoundError, ValueError, OSError):
            continue
        if manifest.get("status") != "SHADOW_RECORDED":
            continue
        try:
            out.append(audit_run(folder))
        except (ValueError, KeyError, FileNotFoundError, OSError) as exc:
            out.append({"run": folder.name, "error": type(exc).__name__ + ":" + str(exc)})
        if len(out) >= last:
            break
    return {
        "examined_completed_runs":len(out),
        "requested_latest_completed_runs":last,
        "runs":out,
        "interpretation":"Use counts to verify input accounting, three private station page completeness and how much was filtered; never interpret it as audited full-universe market deep coverage."
    }


def _f(number):
    return f"{number:,}" if isinstance(number, int) else "NA"


def show(data: dict):
    print("=== V4 recent completed scan counts (local data only) ===")
    for run in data["runs"]:
        if "error" in run:
            print(f"{run['run']}: ERROR {run['error']}")
            continue
        print(
            f"{run['run']}  "
            f"public={_f(run['public_market_raw_order_rows'])} "
            f"active={_f(run['public_market_active_orders_parsed'])} "
            f"4-H={_f(run['stations']['4-H']['raw_orders'])} "
            f"C-J={_f(run['stations']['C-J']['raw_orders'])} "
            f"O4T={_f(run['stations']['O4T']['raw_orders'])} "
            f"public_sell_pairs={_f(run['public_market_sell_station_item_pairs'])} "
            f"global_precheck={_f(run['public_market_global_best_bid_optimistic_pairs'])} "
            f"Jita_deep_pairs={_f(run['market_deep_proofs_examined'])} "
            f"contracts={_f(run['all_public_contracts'])} "
            f"approved_contracts={_f(run['contract_source_and_cash_exchange_approved'])} "
            f"local_QA={'PASS' if run['local_book_coverage_checks_pass'] else 'CHECK'}"
        )
    if data["runs"] and "error" not in data["runs"][0]:
        print("\n=== Three private structures: latest complete run ===")
        row = data["runs"][0]
        for label, lane in row["stations"].items():
            print(
                f"{label}: {lane['raw_orders']} raw, "
                f"{lane['pages_fetched']}/{lane['pages_expected']} pages, "
                f"{lane['active_sell_orders']} active sell orders, "
                f"{lane['sell_item_types']} sell item types, "
                f"{lane['sell_types_with_jita_buy']} types with Jita bids, "
                f"{lane['sell_types_crossed_jita_best_buy']} crossed, "
                f"{lane['sell_types_gross_margin_at_least_50m']} gross >=50m"
            )
        print("\n=== Latest run local accounting checks ===")
        for key, val in row["quality_checks"].items():
            print(f"{key}: {val}")
        print("\nWARNING: 3-structure page-complete + locally accounted data "
              "DOES NOT verify upstream freshness or full-universe market deep coverage.")


def main():
    ap = argparse.ArgumentParser(description="Audit completed V4 scan counts; read only")
    ap.add_argument("--data-root", type=Path, default=Path.home() / "EVE-V4-Data")
    ap.add_argument("--last", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    opts = ap.parse_args()
    result = history(opts.data_root, last=opts.last)
    if opts.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        show(result)


if __name__ == "__main__":
    main()
