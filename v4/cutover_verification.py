"""Read-only post-promotion audit before the Windows Shadow scheduler resumes.

This is NOT the cold archive cryptographic verifier or a restore drill.
The archive and candidate SHA gates run before promotion.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path


def verify(root: Path) -> dict:
    db_path = Path(root).resolve() / "sqlite" / "v4-shadow.sqlite3"
    if not db_path.is_file() or db_path.is_symlink():
        raise RuntimeError("ACTIVE_V4_SQLITE_MISSING")
    uri = "file:" + db_path.resolve().as_posix() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=30)) as db:
        marker_exists = db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='v4_hot_policy'").fetchone()
        index_exists = db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='v4_cold_proofs'").fetchone()
        if not marker_exists or not index_exists:
            raise RuntimeError("CUTOVER_POLICY_OR_COLD_INDEX_ABSENT")
        marker = db.execute(
            "SELECT policy_version,keep_runs,active FROM v4_hot_policy "
            "WHERE singleton=1").fetchone()
        if not marker or marker[0] != 1 or marker[1] != 72 or marker[2] != 1:
            raise RuntimeError("CUTOVER_72_RUN_POLICY_NOT_ACTIVE")
        if db.execute("SELECT COUNT(*) FROM v4_hot_policy").fetchone()[0] != 1:
            raise RuntimeError("CUTOVER_POLICY_MULTIPLE_ROWS")
        if db.execute("PRAGMA auto_vacuum").fetchone()[0] != 2:
            raise RuntimeError("CUTOVER_INCREMENTAL_VACUUM_NOT_ACTIVE")
        records = db.execute(
            "SELECT run_id,proof_count FROM scan_runs "
            "ORDER BY audited_at DESC,run_id DESC").fetchall()
        if not records:
            raise RuntimeError("CUTOVER_EMPTY_LEDGER")
        hot, cold = records[:72], records[72:]
        observed_hot_proofs = 0
        for rid, count in hot:
            n = db.execute(
                "SELECT COUNT(*) FROM proof_versions WHERE run_id=?",
                (rid,)).fetchone()[0]
            if n != count:
                raise RuntimeError("CUTOVER_HOT_RUN_PROOF_MISMATCH:" + rid)
            observed_hot_proofs += n
        for rid, count in cold:
            n = db.execute(
                "SELECT COUNT(*) FROM proof_versions WHERE run_id=?",
                (rid,)).fetchone()[0]
            if n:
                raise RuntimeError("CUTOVER_COLD_RUN_REMAINS_IN_HOT_DB:" + rid)
            record = db.execute(
                "SELECT proof_count FROM v4_cold_proofs WHERE run_id=?",
                (rid,)).fetchone()
            if not record or record[0] != count:
                raise RuntimeError("CUTOVER_COLD_RUN_NOT_INDEXED:" + rid)
        if db.execute("SELECT COUNT(*) FROM v4_cold_proofs").fetchone()[0] != len(cold):
            raise RuntimeError("CUTOVER_COLD_INDEX_EXTRA_OR_INCOMPLETE")
        if db.execute("SELECT COUNT(*) FROM proof_versions").fetchone()[0] != observed_hot_proofs:
            raise RuntimeError("CUTOVER_UNACCOUNTED_HOT_PROOFS")
    return {
        "status": "CUTOVER_72_RUN_POLICY_VERIFIED_READ_ONLY",
        "scan_runs": len(records),
        "detailed_hot_runs": len(hot),
        "cold_indexed_runs": len(cold),
        "hot_proof_rows": observed_hot_proofs,
        "hot_policy_active": True,
        "incremental_auto_vacuum": True,
        "mail_verified": False,
        "recovery_drill_performed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only pre-resume V4 hot cutover audit")
    parser.add_argument("--data-root", type=Path,
                        default=Path.home() / "EVE-V4-Data")
    args = parser.parse_args()
    print(json.dumps(verify(args.data_root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
