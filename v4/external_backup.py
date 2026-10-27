"""Controlled, integrity-checked V4 pre-cutover FULL backup on another volume.

No writes to the source SQLite, no scan, network, mail, or notification.
Read-only inspection by default; --create explicitly writes a new verified
backup on a DIFFERENT Windows volume. This is a maintenance-only tool:
both EVE V4 scheduled tasks must be disabled and the shared scan lock free.

Another Windows volume is not necessarily a different physical device.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sqlite3
import sys
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

from v4.hot_cutover import _check_tasks_disabled, _no_uncheckpointed_sidecars
from v4.local_run import exclusive_lock
from v4.proof_cold_archive import ledger_runs

GIB = 1024 ** 3
MIN_SLACK_GIB = 10


def require_different_volume(root: Path, directory: Path) -> None:
    """Drive test deliberately independent of process-host path semantics."""
    if platform.system() == "Windows":
        a = PureWindowsPath(str(root)).drive.lower()
        b = PureWindowsPath(str(directory)).drive.lower()
        if not a or not b or a == b:
            raise RuntimeError("EXTERNAL_BACKUP_MUST_BE_ON_OTHER_VOLUME")
    if root == directory or root in directory.parents:
        raise RuntimeError("EXTERNAL_BACKUP_MUST_BE_OUTSIDE_DATA_ROOT")


def _safe_directory(root: Path, directory: Path) -> None:
    if directory.is_symlink() or directory.is_file():
        raise RuntimeError("EXTERNAL_BACKUP_DIRECTORY_UNSAFE")
    # Refuse redirection through an existing symlink/junction parent.
    probe = directory
    while probe != probe.parent:
        if probe.exists() and (probe.is_symlink() or (
                platform.system() == "Windows" and
                str(probe.resolve()).lower() != str(probe.absolute()).lower())):
            raise RuntimeError("EXTERNAL_BACKUP_REDIRECTED_DIRECTORY")
        probe = probe.parent
    require_different_volume(root, directory)


def _available_space(directory: Path):
    probe = directory
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return shutil.disk_usage(probe).free


def inspect(root: Path, backup_dir: Path) -> dict:
    root = Path(root).resolve()
    backup_dir = Path(backup_dir).absolute()
    _safe_directory(root, backup_dir)
    source = root / "sqlite" / "v4-shadow.sqlite3"
    if not source.is_file() or source.is_symlink():
        raise RuntimeError("SOURCE_SQLITE_MISSING_OR_UNSAFE")
    free = _available_space(backup_dir)
    needed = source.stat().st_size + MIN_SLACK_GIB * GIB
    return {
        "status": "READ_ONLY_EXTERNAL_BACKUP_INSPECTION",
        "source_size_gib": round(source.stat().st_size / GIB, 3),
        "destination_available_gib": round(free / GIB, 3),
        "space_ready": free >= needed,
        "volume_check": "DIFFERENT_VOLUME" if platform.system() == "Windows"
                        else "NON_WINDOWS_TEST_ONLY",
        "both_scheduled_tasks_must_be_disabled_before_create": True,
        "created": False,
        "source_modified": False,
        "off_machine_copy_still_required": True,
    }


def create(root: Path, backup_dir: Path, *, now=None) -> dict:
    root = Path(root).resolve()
    directory = Path(backup_dir).absolute()
    status = inspect(root, directory)
    if not status["space_ready"]:
        raise RuntimeError("INSUFFICIENT_EXTERNAL_BACKUP_FREE_SPACE")
    # Time-of-check state is not authorization to mutate a live ledger.
    _check_tasks_disabled()
    with exclusive_lock(root / "v4-local-shadow.lock"):
        _check_tasks_disabled()
        source = root / "sqlite" / "v4-shadow.sqlite3"
        # SQLite online backup includes committed WAL frames. The mere
        # presence of -wal/-shm is NOT grounds to refuse a consistent backup;
        # unlike cutover, this operation never renames the source database.
        # SQLite itself must read WAL and enforce transaction consistency.
        before = ledger_runs(root)
        if not before or any(row["status"] != "SHADOW_VERIFIED_OFFLINE"
                             for row in before):
            raise RuntimeError("SOURCE_RUNS_NOT_ALL_VERIFIED")
        moment = now or datetime.now(timezone.utc)
        stamp = moment.strftime("%Y%m%dT%H%M%SZ")
        directory.mkdir(parents=True, exist_ok=True)
        _safe_directory(root, directory)
        target = directory / ("v4-shadow-full-" + stamp + ".sqlite3")
        partial = target.with_name(target.name + ".part")
        if target.exists() or target.is_symlink() or partial.exists() or partial.is_symlink():
            raise FileExistsError("EXTERNAL_BACKUP_TARGET_EXISTS")
        try:
            # Progress diagnostics: SQLite online copy and its subsequent
            # integrity check may each run for many minutes on a 30+ GiB DB.
            # Never log sensitive source rows or credentials.
            last_report = [time.monotonic() - 60.0]
            def progress(status: int, remaining: int, total: int) -> None:
                now_tick = time.monotonic()
                if remaining == 0 or now_tick - last_report[0] >= 30.0:
                    completed = max(0, total - remaining)
                    percent = round(completed * 100.0 / total, 1) if total else 100.0
                    print("BACKUP_COPY_PROGRESS", str(percent) + "%",
                          completed, "of", total, "pages", flush=True,
                          file=sys.stderr)
                    last_report[0] = now_tick
            print("BACKUP_COPY_START", source.stat().st_size, "bytes",
                  flush=True, file=sys.stderr)
            with closing(sqlite3.connect(
                    "file:" + source.as_posix() + "?mode=ro",
                    uri=True, timeout=30)) as live:
                with closing(sqlite3.connect(partial, timeout=30)) as backup:
                    live.backup(backup, pages=2048, sleep=0.1,
                                progress=progress)
                    print("BACKUP_COPY_DONE_INTEGRITY_START",
                          flush=True, file=sys.stderr)
                    if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise RuntimeError("EXTERNAL_BACKUP_INTEGRITY_FAILED")
                    print("BACKUP_INTEGRITY_OK_VERIFYING_LEDGER",
                          flush=True, file=sys.stderr)
                    keys = ("run_id", "status", "proof_count",
                            "proof_sha256", "audited_at")
                    copy_runs = [dict(zip(keys, row)) for row in backup.execute(
                        "SELECT run_id,status,proof_count,proof_sha256,audited_at "
                        "FROM scan_runs ORDER BY audited_at DESC,run_id DESC")]
                    copy_proofs = backup.execute(
                        "SELECT COUNT(*) FROM proof_versions").fetchone()[0]
                    # A backup of a WAL-mode database must be published as a
                    # single self-contained SQLite file. Only checkpoint and
                    # normalize the DESTINATION, never the live source.
                    if backup.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal":
                        ck = backup.execute(
                            "PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                        if not ck or ck[0] != 0:
                            raise RuntimeError("EXTERNAL_BACKUP_WAL_CHECKPOINT_FAILED")
                    if backup.execute(
                            "PRAGMA journal_mode=DELETE").fetchone()[0].lower() != "delete":
                        raise RuntimeError("EXTERNAL_BACKUP_NOT_SELF_CONTAINED")
            # Reject a copied DB that depends on transient WAL/SHM/journal.
            _no_uncheckpointed_sidecars(partial)
            with closing(sqlite3.connect(
                    "file:" + partial.resolve().as_posix() + "?mode=ro&immutable=1",
                    uri=True, timeout=30)) as immutable:
                if immutable.execute(
                        "PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("EXTERNAL_BACKUP_STANDALONE_INTEGRITY_FAILED")
                if immutable.execute(
                        "SELECT COUNT(*) FROM proof_versions").fetchone()[0] != copy_proofs:
                    raise RuntimeError("EXTERNAL_BACKUP_STANDALONE_PROOFS_MISMATCH")
            after = ledger_runs(root)
            # Verify copied records against the current logical SQLite view.
            # Do NOT rely on parsing the bare .sqlite3 while WAL exists.
            if after != before or copy_runs != before or (
                    copy_proofs != sum(x["proof_count"] for x in before)):
                raise RuntimeError("EXTERNAL_BACKUP_NOT_CURRENT_OR_INCOMPLETE")
            # Persist only after all audit checks completed successfully.
            os.replace(partial, target)
            print("BACKUP_VERIFIED_PUBLISHED", target, flush=True,
                  file=sys.stderr)
            return {
                "status": "FULL_EXTERNAL_BACKUP_VERIFIED",
                "path": str(target), "bytes": target.stat().st_size,
                "sqlite_integrity": "ok", "scan_runs": len(copy_runs),
                "proof_rows": copy_proofs,
                "source_database_modified": False,
                "off_machine_copy_still_required": True,
            }
        finally:
            # Only this tool's OWN explicitly named temporary output is removed.
            partial.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="V4 external pre-cutover full backup")
    parser.add_argument("--data-root", type=Path,
                        default=Path.home() / "EVE-V4-Data")
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--create", action="store_true",
                        help="Explicitly create an external full SQLite backup")
    args = parser.parse_args()
    report = (create(args.data_root, args.backup_dir) if args.create
              else inspect(args.data_root, args.backup_dir))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
