"""Guarded, WAL-aware SQLite checkpoint prior to V4 hot/cold promotion.

Read-only by default. --apply can change ONLY the LIVE SQLite journal
metadata/checkpoint, after independently verifying a CURRENT full backup
on another Windows volume. It cannot replace a database or delete artifacts.

Do not delete -wal/-shm/-journal manually: SQLite must close them itself.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from v4.hot_cutover import (
    _check_tasks_disabled, _no_uncheckpointed_sidecars,
    _verified_independent_backup,
)
from v4.local_run import exclusive_lock
from v4.proof_cold_archive import ledger_runs

ACK = "I_ACCEPT_V4_SQLITE_CHECKPOINT"


def _sidecars(source: Path) -> dict:
    return {
        ending: {"present": (p := source.with_name(source.name + ending)).exists(),
                 "bytes": p.stat().st_size if p.is_file() else None}
        for ending in ("-wal", "-shm", "-journal")
    }


def inspect(root: Path) -> dict:
    root = Path(root).resolve()
    source = root / "sqlite" / "v4-shadow.sqlite3"
    if not source.is_file() or source.is_symlink():
        raise RuntimeError("LIVE_SQLITE_MISSING_OR_UNSAFE")
    return {
        "status": "READ_ONLY_WAL_CHECKPOINT_INSPECTION",
        "sidecars": _sidecars(source),
        "backup_verified": False,
        "source_modified": False,
        "checkpoint_performed": False,
        "hot_cutover_performed": False,
        "requires_both_tasks_disabled": True,
        "requires_current_different_volume_full_backup": True,
    }


def checkpoint(root: Path, *, external_backup: Path, acknowledgement: str) -> dict:
    """Finalize SQLite journal mode in a controlled, quiet maintenance window."""
    if acknowledgement != ACK:
        raise RuntimeError("OPERATOR_EXPLICIT_CHECKPOINT_ACK_REQUIRED")
    root = Path(root).resolve()
    source = root / "sqlite" / "v4-shadow.sqlite3"
    if not source.is_file() or source.is_symlink():
        raise RuntimeError("LIVE_SQLITE_MISSING_OR_UNSAFE")
    _check_tasks_disabled()
    with exclusive_lock(root / "v4-local-shadow.lock"):
        _check_tasks_disabled()
        # This uses read-only WAL-AWARE queries for the live source and
        # immutable read-only verification for the self-contained backup.
        # It checks EVERY scan-run record/hash and the total proof count,
        # and integrity_check on the external backup, BEFORE source changes.
        verified = _verified_independent_backup(
            root, Path(external_backup))
        before = ledger_runs(root)
        journal = source.with_name(source.name + "-journal")
        if journal.exists():
            raise RuntimeError("ROLLBACK_JOURNAL_PRESENT_DO_NOT_TOUCH")
        previous_sidecars = _sidecars(source)
        with closing(sqlite3.connect(source, timeout=30)) as db:
            db.execute("PRAGMA busy_timeout=30000")
            initial_mode = db.execute("PRAGMA journal_mode").fetchone()[0].lower()
            if initial_mode not in ("wal", "delete"):
                raise RuntimeError("UNSUPPORTED_LIVE_JOURNAL_MODE")
            checkpoint_stats = None
            if initial_mode == "wal":
                checkpoint_stats = db.execute(
                    "PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                if checkpoint_stats is None or checkpoint_stats[0] != 0:
                    raise RuntimeError("WAL_CHECKPOINT_BUSY_OR_FAILED")
            # SQLite, not the application filesystem, transitions the journal
            # mode and removes its own shared-memory/WAL sidecars on close.
            result_mode = db.execute(
                "PRAGMA journal_mode=DELETE").fetchone()
            if result_mode is None or result_mode[0].lower() != "delete":
                raise RuntimeError("SQLITE_COULD_NOT_LEAVE_WAL_MODE")
        # If an external reader holds WAL open, this will fail closed rather
        # than silently bypassing the strict cutover-sidecar safety gate.
        _no_uncheckpointed_sidecars(source)
        after = ledger_runs(root)
        if after != before:
            raise RuntimeError("CHECKPOINT_CHANGED_AUDITED_RUNS")
        with closing(sqlite3.connect(
                "file:" + source.resolve().as_posix() + "?mode=ro&immutable=1",
                uri=True, timeout=30)) as immutable:
            if immutable.execute(
                    "PRAGMA journal_mode").fetchone()[0].lower() != "delete":
                raise RuntimeError("SOURCE_STILL_WAL_MODE")
            # Existing backup was checked fully before touching source.
            if immutable.execute(
                    "PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("SOURCE_SQLITE_QUICK_CHECK_FAILED")
        # Compare again with the external backup after SQLite checkpointing.
        _verified_independent_backup(root, Path(external_backup))
        return {
            "status": "SOURCE_CHECKPOINTED_NO_CUTOVER",
            "source_db": str(source),
            "previous_journal_mode": initial_mode,
            "current_journal_mode": "delete",
            "wal_checkpoint_stats": list(checkpoint_stats)
                                    if checkpoint_stats is not None else None,
            "before_sidecars": previous_sidecars,
            "after_sidecars": _sidecars(source),
            "external_backup": verified,
            "scan_runs_unchanged": len(after),
            "hot_cutover_performed": False,
            "source_removed": False,
            "no_manual_sidecar_deletion": True,
        }


def main():
    p = argparse.ArgumentParser(
        description="V4 guarded WAL checkpoint after verified full external backup")
    p.add_argument("--data-root", type=Path,
                   default=Path.home() / "EVE-V4-Data")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--external-backup", type=Path)
    p.add_argument("--ack", default="")
    args = p.parse_args()
    if args.apply:
        if args.external_backup is None:
            p.error("--apply requires --external-backup")
        output = checkpoint(args.data_root, external_backup=args.external_backup,
                            acknowledgement=args.ack)
    else:
        output = inspect(args.data_root)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
