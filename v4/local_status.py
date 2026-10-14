"""Local V4 shadow diagnostic: read-only and safe to share (no token/path output)."""
from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path


def inspect(root: Path) -> dict:
    root = Path(root).resolve()
    runs = root / "runs"
    latest = sorted((p for p in runs.iterdir() if p.is_dir()), reverse=True) if runs.is_dir() else []
    if not latest:
        raise FileNotFoundError("NO_LOCAL_RUNS")
    folder = latest[0]
    manifest = json.loads((folder / "manifest.json").read_text("utf-8"))
    result = {
        "latest_run_folder_name": folder.name,
        "run_status": manifest.get("status"),
        "coverage_gate": manifest.get("coverage_gate"),
        "mail_enabled": False,
        "ready_for_production": False,
        "paths_redacted": True,
    }
    deepfile = folder / "deep_shadow.json"
    fullfile = folder / "full_market_report.json"
    if fullfile.is_file():
        full = json.loads(fullfile.read_text("utf-8"))
        result["full_census_status"] = full.get("overall")
        result["raw_market_orders"] = (full.get("market") or {}).get("market_raw_rows")
        result["snapshots"] = {
            key: {
                "status": value.get("status"),
                "age_hours": value.get("age_hours"),
                "last_modified": value.get("last_modified"),
                "compressed_bytes": value.get("compressed_bytes"),
            }
            for key, value in (full.get("sources") or {}).items()
        }
    if not deepfile.is_file():
        result["missing_deep_shadow_report"] = True
        return result
    deep = json.loads(deepfile.read_text("utf-8"))
    health = deep.get("structure_health") or {}
    result.update({
        "run_id": deep.get("run_id"),
        "public_market_orders_parsed": deep.get("public_market_orders"),
        "authorized_structure_orders_parsed": deep.get("authorized_structure_orders"),
        "rejected_input_orders": deep.get("rejected_input_orders"),
        "invalid_public_orders": deep.get("invalid_public_orders"),
        "invalid_structure_orders": deep.get("invalid_structure_orders"),
        "zero_remaining_public_orders": deep.get("zero_remaining_public_orders"),
        "zero_remaining_structure_orders": deep.get("zero_remaining_structure_orders"),
        "non_actionable_zero_remaining_orders": deep.get("non_actionable_zero_remaining_orders"),
        "source_input_integrity": deep.get("source_input_integrity"),
        "market_potential_pairs": deep.get("market_potential_pairs"),
        "contract_rows": deep.get("contract_rows"),
        "proof_count_in_report": deep.get("proof_count"),
        "model_candidates": deep.get("model_candidates"),
        "formal_candidates": deep.get("formal_candidates"),
        "structure_health": {
            key: {
                "status": val.get("status"),
                "reason": val.get("reason"),
                "orders": val.get("orders"),
                "pages": val.get("pages"),
                "pages_fetched": val.get("pages_fetched"),
                "failed_page": val.get("failed_page"),
                "attempts_on_failed_page": val.get("attempts_on_failed_page"),
                "transient_retries": val.get("transient_retries"),
            }
            for key, val in health.items()
        },
        "proof_reasons_top": dict(sorted((deep.get("reason_counts") or {}).items(),
                                         key=lambda x: -x[1])[:12]),
    })
    database = root / "sqlite" / "v4-shadow.sqlite3"
    if not database.is_file():
        result["sqlite_status"] = "MISSING"
        return result
    with closing(sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)) as con:
        status = con.execute("PRAGMA integrity_check").fetchone()[0]
        row = con.execute(
            "SELECT status, proof_count FROM scan_runs WHERE run_id=?",
            (deep.get("run_id"),)).fetchone()
        unique_count = con.execute(
            "SELECT COUNT(*) FROM proof_versions WHERE run_id=?",
            (deep.get("run_id"),)).fetchone()[0]
        results = dict(con.execute(
            "SELECT status, COUNT(*) FROM proof_versions WHERE run_id=? GROUP BY status",
            (deep.get("run_id"),)).fetchall())
    result.update({
        "sqlite_integrity": status,
        "sqlite_run_row": row[0] if row else None,
        "sqlite_unique_proofs": unique_count,
        "sqlite_status_counts": results,
        "sqlite_count_matches_report": (status == "ok" and row is not None
                                        and row[1] == unique_count == deep.get("proof_count")),
        "shadow_only": True,
        "mail_enabled": False,
        "ready_for_production": False,
    })
    return result


def main():
    p = argparse.ArgumentParser(description="Inspect latest V4 shadow run and local SQLite read-only")
    p.add_argument("--data-root", type=Path, default=Path.home() / "EVE-V4-Data")
    args = p.parse_args()
    print(json.dumps(inspect(args.data_root), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
