"""Independently scheduled V4 daily SQLite backup.

This module is designed for its OWN Windows Task Scheduler job, not for the
hourly scan/mail process. It does not take the V4 scan mutex, so daily
integrity checks cannot hold that mutex or postpone mail. SQLite's online
backup API provides a consistent snapshot of committed data including WAL.

Never enable hourly --backup-mode external until this separate daily task has
been successfully installed, checked and enabled.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from pathlib import Path

from v4.local_backup import backup
from v4.local_run import exclusive_lock
from v4.storage_retention import rotate_backups

GIB = 1024 ** 3
REQUIRED_FREE_SLACK_GIB = 20


def scheduled_day_due(root: Path, now: datetime) -> bool:
    """One verified local backup per machine-local calendar day, not 24h elapsed.

    A backup manually created at 09:46 must not suppress the next scheduled
    03:45 backup on the following local date. Use local dates to agree with the
    Windows Task Scheduler's daily local trigger.
    """
    backups = root / "backups"
    latest = max(backups.glob("v4-shadow-*.sqlite3"),
                 key=lambda p: p.stat().st_mtime,
                 default=None) if backups.exists() else None
    if latest is None:
        return True
    latest_local_date = datetime.fromtimestamp(
        latest.stat().st_mtime, tz=timezone.utc).astimezone().date()
    return latest_local_date < now.astimezone().date()


def perform(data_root: Path, *, backup_fn=backup,
            rotate_fn=rotate_backups,
            now_fn=lambda: datetime.now(timezone.utc)) -> dict:
    root = Path(data_root).resolve()
    source = root / "sqlite" / "v4-shadow.sqlite3"
    if not source.is_file() or source.is_symlink():
        raise RuntimeError("DAILY_BACKUP_SOURCE_MISSING_OR_UNSAFE")
    # Independent backup-only mutex prevents duplicate daily copies.
    # It does not block hourly scans or mail.
    with exclusive_lock(root / "v4-daily-backup-job.lock"):
        if not scheduled_day_due(root, now_fn()):
            return {"status": "NOT_DUE", "backup_created": False}
        free = shutil.disk_usage(root).free
        needed = source.stat().st_size + REQUIRED_FREE_SLACK_GIB * GIB
        if free < needed:
            return {
                "status": "BLOCKED_INSUFFICIENT_SPACE",
                "backup_created": False,
                "free_gib": round(free / GIB, 2),
                "needed_gib": round(needed / GIB, 2),
            }
        print("DAILY_BACKUP_JOB_START", flush=True)
        saved = backup_fn(root)
        if (saved.get("sqlite_integrity") != "ok" or
                not saved.get("ok") or not saved.get("path")):
            raise RuntimeError("DAILY_BACKUP_NOT_VERIFIED")
        # Failure of retention may NOT destroy the newest valid backup.
        try:
            rotation = rotate_fn(root, apply=True,
                                 expected_newest=Path(saved["path"]))
        except Exception as exc:
            rotation = {
                "status": "BLOCKED", "error_type": type(exc).__name__,
                "newest_backup_preserved": True,
            }
        return {
            "status": "DAILY_BACKUP_VERIFIED",
            "backup_created": True,
            "backup_path": saved["path"],
            "scan_runs": saved.get("scan_runs"),
            "proof_versions": saved.get("proof_versions"),
            "backup_retention": rotation,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="V4 separate daily SQLite backup")
    parser.add_argument("--data-root", type=Path,
                        default=Path.home() / "EVE-V4-Data")
    args = parser.parse_args()
    root = args.data_root.resolve()
    logs = root / "logs"
    try:
        logs.mkdir(parents=True, exist_ok=True)
        with (logs / "daily-backup-task.log").open("a", encoding="utf-8") as log:
            with redirect_stdout(log), redirect_stderr(log):
                print("DAILY_BACKUP_TASK_STARTED",
                      datetime.now(timezone.utc).isoformat(), flush=True)
                try:
                    result = perform(root)
                    print("DAILY_BACKUP_TASK_RESULT",
                          json.dumps(result, ensure_ascii=False), flush=True)
                    return 0 if result["status"] in (
                        "DAILY_BACKUP_VERIFIED", "NOT_DUE") else 4
                except Exception as exc:
                    print("DAILY_BACKUP_TASK_FAILED",
                          type(exc).__name__, str(exc), flush=True)
                    traceback.print_exc(file=log)
                    return 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
