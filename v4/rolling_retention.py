"""Read-only 72-successful-scan retention inventory for the Windows V4 worker.

This module NEVER deletes files or SQL rows. A report marked eligible is only
a candidate for the separately gated future cleanup transaction.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

KEEP_SUCCESSFUL_RUNS = 72
GOOD_STATUS = "SHADOW_VERIFIED_OFFLINE"
GOOD_COVERAGE = "INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED"
KNOWN_RECEIPT_ROOTS = (
    "mail-review/receipts", "mail-review/eve-receipts"
)


def _inside(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _json(path: Path) -> dict | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _folders(root: Path) -> tuple[dict[str, Path], list[str]]:
    result: dict[str, Path] = {}
    duplicates: set[str] = set()
    folder = root / "runs"
    if not folder.is_dir() or folder.is_symlink():
        return result, ["RUNS_DIRECTORY_MISSING_OR_UNSAFE"]
    for item in folder.iterdir():
        if not item.is_dir() or item.is_symlink():
            continue
        detail = _json(item / "deep_shadow.json")
        if not detail:
            continue
        run_id = detail.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            continue
        if run_id in result:
            duplicates.add(run_id)
        else:
            result[run_id] = item
    for run_id in duplicates:
        result.pop(run_id, None)
    return result, sorted("DUPLICATE_RUN_ID:" + x for x in duplicates)


def _complete(folder: Path) -> bool:
    manifest = _json(folder / "manifest.json")
    return bool(manifest and
                manifest.get("status") == "SHADOW_RECORDED" and
                manifest.get("coverage_gate") == GOOD_COVERAGE and
                manifest.get("source_input_integrity") == "ALL_PARSED" and
                manifest.get("failed_structure_lanes") in ({}, None))


def _bytes_of(folder: Path) -> int | None:
    """Only inventory directories, never traverse a junction or symlink."""
    if folder.is_symlink() or not folder.is_dir():
        return None
    total = 0
    for parent, dirs, files in os.walk(folder, followlinks=False):
        current = Path(parent)
        for d in dirs:
            if (current / d).is_symlink():
                return None
        for name in files:
            path = current / name
            if path.is_symlink() or not path.is_file():
                return None
            total += path.stat().st_size
    return total


def inspect(root: Path, *, keep_runs: int = KEEP_SUCCESSFUL_RUNS) -> dict:
    if keep_runs != KEEP_SUCCESSFUL_RUNS:
        raise ValueError("V4_RETENTION_POLICY_REQUIRES_EXACTLY_72")
    root = Path(root).resolve()
    db_path = root / "sqlite" / "v4-shadow.sqlite3"
    report = {
        "status": "READ_ONLY_72_RUN_RETENTION_INSPECTION",
        "retention_policy": "LATEST_72_SUCCESSFUL_SCANS",
        "keep_successful_runs": keep_runs,
        "data_deleted": False,
        "sqlite_modified": False,
        "requires_migration_and_verified_backup": True,
        "current_successful_runs": 0,
        "retained_successful_runs": 0,
        "historical_success_runs": 0,
        "ready_for_further_verification": 0,
        "blocked_old_runs": 0,
        "potential_raw_reclaim_gib": 0.0,
        "old_run_samples": [],
        "warnings": [],
    }
    if not db_path.is_file() or db_path.is_symlink():
        return {**report, "status": "BLOCKED_NO_SAFE_LIVE_SQLITE"}
    folders, warnings = _folders(root)
    report["warnings"].extend(warnings)
    uri = "file:" + db_path.as_posix() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=30)) as db:
        db.execute("PRAGMA query_only=ON")
        runs = db.execute(
            "SELECT run_id, status, audited_at FROM scan_runs "
            "ORDER BY audited_at DESC, run_id DESC").fetchall()
        good = [(run_id, audited_at, folders.get(run_id))
                for run_id, status, audited_at in runs
                if status == GOOD_STATUS and folders.get(run_id)
                and _complete(folders[run_id])]
        report["current_successful_runs"] = len(good)
        report["retained_successful_runs"] = min(len(good), keep_runs)
        old = good[keep_runs:]
        report["historical_success_runs"] = len(old)
        sizes = 0
        for run_id, audited_at, folder in old:
            issues: list[str] = []
            proof_count = db.execute(
                "SELECT COUNT(*) FROM proof_versions WHERE run_id=?",
                (run_id,)).fetchone()[0]
            if proof_count:
                issues.append("HOT_SQL_PROOFS_NOT_YET_PRUNED")
            # Never assume success means both independent mail channels delivered.
            gmail = root / KNOWN_RECEIPT_ROOTS[0] / (folder.name + ".json")
            game = root / KNOWN_RECEIPT_ROOTS[1] / (folder.name + ".json")
            baba = root / KNOWN_RECEIPT_ROOTS[1] / (folder.name + "-2124729692.json")
            if not _json(gmail):
                issues.append("GMAIL_RECEIPT_UNVERIFIED")
            if not _json(game):
                issues.append("MIKECHONG_RECEIPT_UNVERIFIED")
            if not _json(baba):
                issues.append("LADYBABA_RECEIPT_UNVERIFIED")
            byte_count = _bytes_of(folder)
            if byte_count is None or not _inside(root / "runs", folder):
                issues.append("RUN_DIRECTORY_UNSAFE")
            if not issues:
                report["ready_for_further_verification"] += 1
                sizes += byte_count
            else:
                report["blocked_old_runs"] += 1
            if len(report["old_run_samples"]) < 12:
                report["old_run_samples"].append({
                    "run_id": run_id, "run_folder": folder.name,
                    "audited_at": audited_at,
                    "raw_gib": (None if byte_count is None else
                                round(byte_count / 1024**3, 4)),
                    "blockers": issues,
                })
        report["potential_raw_reclaim_gib"] = round(sizes / 1024**3, 3)
        report["unmapped_sqlite_rows"] = len(runs) - sum(
            1 for run_id, _, _ in runs if run_id in folders)
        if report["unmapped_sqlite_rows"]:
            report["warnings"].append("UNMAPPED_SQLITE_ROWS_REQUIRE_SEPARATE_MIGRATION")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only V4 72 successful scans inventory")
    parser.add_argument("--data-root", type=Path, default=Path.home() / "EVE-V4-Data")
    args = parser.parse_args()
    print(json.dumps(inspect(args.data_root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
