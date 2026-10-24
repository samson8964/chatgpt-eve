"""Conservative V4 daily SQLite backup retention.

No historical proof row, market snapshot, live SQLite database, scan log,
or opportunity receipt is modified. The *only* removable files are older
verified, exactly named local SQLite backups. Default CLI is dry-run.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from v4.local_run import exclusive_lock

KEEP = 3
BACKUP_NAME = re.compile(r"^v4-shadow-(\d{8})T\d{6}Z\.sqlite3$")


def _backups(root: Path) -> list[Path]:
    folder = root / "backups"
    if not folder.exists():
        return []
    if folder.is_symlink() or not folder.is_dir():
        raise RuntimeError("BACKUP_FOLDER_UNSAFE")
    results = []
    for item in folder.iterdir():
        if not BACKUP_NAME.fullmatch(item.name):
            continue
        if item.is_symlink() or not item.is_file():
            raise RuntimeError("BACKUP_FILE_UNSAFE")
        results.append(item)
    # Backup names contain a sortable UTC timestamp. Newest comes first.
    return sorted(results, key=lambda p: p.name, reverse=True)


def _meta(files: list[Path]) -> list[tuple[str, int, int]]:
    return [(p.name, p.stat().st_size, p.stat().st_mtime_ns) for p in files]


def _check_sqlite(path: Path) -> None:
    """Read-only structural check; source is immutable during retention."""
    uri = "file:" + path.resolve().as_posix() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True, timeout=30)) as db:
        row = db.execute("PRAGMA quick_check").fetchone()
        if not row or row[0] != "ok":
            raise RuntimeError("RETAINED_BACKUP_SQLITE_CHECK_FAILED")
        tables = {r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if not {"proof_versions", "scan_runs"}.issubset(tables):
            raise RuntimeError("RETAINED_BACKUP_SCHEMA_INVALID")
        count = db.execute("SELECT COUNT(*) FROM scan_runs").fetchone()[0]
        if not isinstance(count, int) or count <= 0:
            raise RuntimeError("RETAINED_BACKUP_NO_RUNS")


def rotate_backups(data_root: Path, *, apply: bool = False,
                   expected_newest: Path | None = None) -> dict:
    """Keep latest 3 distinct-day valid backups; fail closed before unlink.

    Call after backup() returned sqlite_integrity='ok'. The strict expected
    newest check is used by automatic post-backup retention. CLI defaults
    to preview; --apply intentionally removes old local backup files.
    """
    root = Path(data_root).resolve()
    # Independent maintenance lock: verification of 20+ GiB backups must
    # never occupy the opportunity/scan mutex and delay live alerts.
    with exclusive_lock(root / "v4-backup-retention.lock"):
        files = _backups(root)
        records = _meta(files)
        retain = files[:KEEP]
        old = files[KEEP:]
        bytes_old = sum(p.stat().st_size for p in old)
        result = {
            "status": "DRY_RUN" if not apply else "NOT_NEEDED",
            "retained": [p.name for p in retain],
            "old_backups": len(old),
            "potential_reclaim_gib": round(bytes_old / (1024**3), 2),
            "deleted": 0,
            "off_machine_backup_still_required": True,
        }
        if expected_newest is not None:
            if not files or files[0].resolve() != Path(expected_newest).resolve():
                raise RuntimeError("NEW_BACKUP_NOT_LATEST")
        if len(files) <= KEEP or not apply:
            return result
        # Avoid deleting historical restore points when all recent copies
        # were accidentally created on the same calendar day.
        days = {BACKUP_NAME.fullmatch(p.name).group(1) for p in retain}
        if len(days) != KEEP:
            return {**result, "status": "BLOCKED_RECENT_DAYS_NOT_DISTINCT"}
        # All kept local restore points must pass basic structural checks.
        # A newly created backup has ALREADY passed full integrity_check in
        # v4.local_backup.backup before reaching this function.
        for path in retain:
            _check_sqlite(path)
        # If the source changes during checks, avoid decisions on stale data.
        if _meta(_backups(root)) != records:
            raise RuntimeError("BACKUP_SET_CHANGED_DURING_CHECK")
        freed = 0
        for path in old:
            size = path.stat().st_size
            path.unlink()
            freed += size
        return {
            **result, "status": "ROTATED",
            "deleted": len(old),
            "reclaimed_gib": round(freed / (1024**3), 2),
        }


def main() -> None:
    p = argparse.ArgumentParser(description="V4 local verified backup rotation")
    p.add_argument("--data-root", type=Path,
                   default=Path.home() / "EVE-V4-Data")
    p.add_argument("--apply", action="store_true",
                   help="Delete older backups after verifying 3 recent copies")
    args = p.parse_args()
    report = rotate_backups(args.data_root, apply=args.apply)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
