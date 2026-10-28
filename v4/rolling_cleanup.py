"""Fail-closed, resumable V4 72-successful-run storage cleanup.

Opt-in and disabled until a separate-volume backup has been verified.
Unlike the old proof-only retainer this removes old SQL rows and raw folders.
Never touches SQLite WAL/SHM, backup files, logs or credential/config files.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import stat
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from v4.local_run import exclusive_lock
from v4.rolling_retention import _folders, _complete, _json, GOOD_STATUS

KEEP = 72
MAX_PER_CYCLE = 2
TOKEN = "V4_ROLLING_72_VERIFIED_EXTERNAL_BACKUP_V1"
POLICY = Path("config/rolling72-enabled.json")
RUN_DIR = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")
RUN_ID = re.compile(r"^[A-Za-z0-9_-]{5,128}$")


def _safe(path: Path, root: Path, *, directory: bool = False) -> bool:
    """Reject symlinks and Windows junction/reparse points at every level."""
    try:
        if not path.absolute().is_relative_to(root.absolute()):
            return False
        for part in [path, *list(path.parents)]:
            if part == root.parent:
                break
            if part.is_symlink():
                return False
            if part.exists():
                mode = part.stat(follow_symlinks=False)
                if getattr(mode, "st_file_attributes", 0) & getattr(
                        stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
                    return False
        if directory and not path.is_dir():
            return False
        return True
    except (OSError, ValueError):
        return False


def _safe_tree(path: Path, root: Path) -> bool:
    if not _safe(path, root, directory=True):
        return False
    for base, dirs, files in os.walk(path, followlinks=False):
        parent = Path(base)
        for name in dirs + files:
            item = parent / name
            if not _safe(item, root):
                return False
    return True


def _table(db, name: str) -> bool:
    return bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                           (name,)).fetchone())


def _mail_guards(root: Path, folder: Path) -> list[str]:
    """Require receipts only for enabled channels, with their *actual* IDs."""
    issues = []
    from v4.research_mail import _config
    from v4.game_mail_review import read_settings, _recipient_receipt
    try:
        if _config(root) is not None:
            path = root / "mail-review" / "receipts" / (folder.name + ".json")
            item = _json(path)
            if not item or item.get("run") != folder.name or not item.get("sent_at"):
                issues.append("GMAIL_UNCONFIRMED")
        settings = read_settings(root)
        if settings is not None:
            for recipient in settings["recipients"]:
                options = _recipient_receipt(root, folder.name, recipient)
                if not any((lambda x: x is not None and
                            x.get("run") == folder.name and
                            x.get("recipient_id") == recipient["id"] and
                            bool(x.get("confirmed_at")))(_json(path))
                           for path in options):
                    issues.append("GAME_MAIL_UNCONFIRMED:" + recipient["name"])
    except Exception:
        issues.append("MAIL_CONFIGURATION_UNKNOWN")
    return issues


def _history(root: Path, db) -> tuple[list, list[str]]:
    """Only full coverage, already persisted, manifest-matching successes."""
    folders, warnings = _folders(root)
    if warnings:
        return [], warnings
    rows = db.execute(
        "SELECT run_id,status,audited_at,proof_count,proof_sha256 "
        "FROM scan_runs ORDER BY audited_at DESC,run_id DESC").fetchall()
    successes = []
    for run_id, status, audit_at, proof_count, sha in rows:
        folder = folders.get(run_id)
        if (status != GOOD_STATUS or folder is None or not _complete(folder)
                or not RUN_DIR.fullmatch(folder.name)
                or not RUN_ID.fullmatch(run_id)):
            continue
        manifest = _json(folder / "manifest.json")
        if (manifest.get("proofs_sha256") != sha or
                manifest.get("sqlite_unique_proofs") != proof_count):
            continue
        successes.append((run_id, folder.name, audit_at, proof_count, sha))
    return successes, []


def _pending(db) -> list[tuple[str, str]]:
    if not _table(db, "rolling72_pending"):
        return []
    return db.execute(
        "SELECT run_id,folder_name FROM rolling72_pending ORDER BY created_at,run_id"
    ).fetchall()


def plan(root: Path) -> dict:
    root = Path(root).resolve()
    dbfile = root / "sqlite" / "v4-shadow.sqlite3"
    output = dict(status="READ_ONLY", keep_successful_runs=KEEP, activated=False,
                  current_successful_runs=0, old_run_count=0, eligible=0,
                  blocked=0, pending=0, examples=[], modified=False)
    policy = _json(root / POLICY)
    output["activated"] = bool(policy and policy.get("schema") == 1 and
                               policy.get("token") == TOKEN)
    if not dbfile.is_file() or not _safe(dbfile, root):
        return {**output, "status": "BLOCKED_UNSAFE_SQLITE"}
    with closing(sqlite3.connect("file:" + dbfile.as_posix() + "?mode=ro",
                                 uri=True, timeout=30)) as db:
        db.execute("PRAGMA query_only=ON")
        rows, warnings = _history(root, db)
        output["current_successful_runs"] = len(rows)
        output["pending"] = len(_pending(db))
        old = rows[KEEP:]
        output["old_run_count"] = len(old)
        output["warnings"] = warnings
        for run_id, folder_name, _, _, _ in old:
            folder = root / "runs" / folder_name
            blockers = _mail_guards(root, folder)
            if not _safe_tree(folder, root / "runs"):
                blockers.append("UNSAFE_DIRECTORY")
            if blockers:
                output["blocked"] += 1
            else:
                output["eligible"] += 1
            if len(output["examples"]) < 10:
                output["examples"].append(
                    {"run_id": run_id, "folder": folder_name, "blockers": blockers})
    return output


def _require_activation(root: Path) -> None:
    data = _json(root / POLICY)
    if not (data and data.get("schema") == 1 and data.get("token") == TOKEN
            and data.get("backed_up") is True and
            isinstance(data.get("backup"), str)):
        raise RuntimeError("ROLLING72_NOT_ACTIVATED_WITH_VERIFIED_BACKUP")
    backup = Path(data["backup"])
    if not backup.is_file() or not _safe(backup, backup.parent):
        raise RuntimeError("ROLLING72_EXTERNAL_BACKUP_MISSING_OR_UNSAFE")
    if os.path.splitdrive(str(backup.resolve()))[0].lower() == (
            os.path.splitdrive(str(root.resolve()))[0].lower()):
        raise RuntimeError("ROLLING72_BACKUP_NOT_ON_OTHER_VOLUME")


def activate(root: Path, *, backup: Path) -> dict:
    """Explicit one-time acknowledgement, after independent full backup.

    A matching snapshot is mandatory; never automatically enabled by git pull.
    """
    root, backup = Path(root).resolve(), Path(backup).resolve()
    if os.name != "nt":
        raise RuntimeError("ROLLING72_ACTIVATION_ONLY_ON_WINDOWS")
    if (not backup.is_file() or not _safe(backup, backup.parent) or
            os.path.splitdrive(str(root))[0].lower() ==
            os.path.splitdrive(str(backup))[0].lower()):
        raise RuntimeError("ROLLING72_REQUIRES_OTHER_VOLUME_BACKUP")
    if (root / POLICY).exists():
        raise RuntimeError("ROLLING72_ALREADY_CONFIGURED")
    source = root / "sqlite" / "v4-shadow.sqlite3"
    with closing(sqlite3.connect("file:" + backup.as_posix() +
                                 "?mode=ro&immutable=1", uri=True)) as check:
        if check.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise RuntimeError("ROLLING72_BACKUP_INTEGRITY_FAILED")
        if not _table(check, "scan_runs"):
            raise RuntimeError("ROLLING72_BACKUP_SCHEMA_INVALID")
        backup_latest = check.execute(
            "SELECT run_id FROM scan_runs ORDER BY audited_at DESC,run_id DESC LIMIT 1"
        ).fetchone()
    with closing(sqlite3.connect("file:" + source.as_posix() + "?mode=ro",
                                 uri=True)) as live:
        live_latest = live.execute(
            "SELECT run_id FROM scan_runs ORDER BY audited_at DESC,run_id DESC LIMIT 1"
        ).fetchone()
    if not backup_latest or backup_latest != live_latest:
        raise RuntimeError("ROLLING72_BACKUP_NOT_CURRENT")
    record = dict(schema=1, token=TOKEN, backed_up=True,
                  backup=str(backup), activated_at=datetime.now(timezone.utc).isoformat(),
                  backup_latest_run=backup_latest[0])
    policy = root / POLICY
    policy.parent.mkdir(parents=True, exist_ok=True)
    with policy.open("x", encoding="utf-8") as fp:
        json.dump(record, fp, indent=2)
    return dict(status="ROLLING72_ACTIVATED", backup=str(backup),
                automatic_delete_now_allowed=True)



def _purge_auxiliary(root: Path, run_id: str, folder_name: str) -> int:
    """Purge only old-run cold artifacts and receipts, by exact verified names.

    Resumable: archive is removed first, manifest last; missing archive with a
    valid manifest means previous partial completion. Unknown archive without
    a manifest is not guessed safe.
    """
    freed = 0
    cold = root / "cold-proof-archives"
    if cold.exists():
        if not _safe(cold, root, directory=True):
            raise RuntimeError("ROLLING72_COLD_DIRECTORY_UNSAFE")
        manifest = cold / (run_id + ".manifest.json")
        archive = cold / (run_id + ".jsonl.gz")
        if not _safe(manifest, root) or not _safe(archive, root):
            raise RuntimeError("ROLLING72_COLD_ARTIFACT_UNSAFE")
        if manifest.exists():
            data = _json(manifest)
            if not data or data.get("run_id") != run_id:
                raise RuntimeError("ROLLING72_COLD_MANIFEST_MISMATCH")
            if archive.exists():
                freed += archive.stat().st_size
                archive.unlink()
            freed += manifest.stat().st_size
            manifest.unlink()
        elif archive.exists():
            raise RuntimeError("ROLLING72_ORPHAN_COLD_ARCHIVE")
    for relative in ("mail-review/receipts", "mail-review/eve-receipts"):
        directory = root / relative
        if not directory.exists():
            continue
        if not _safe(directory, root, directory=True):
            raise RuntimeError("ROLLING72_RECEIPT_DIRECTORY_UNSAFE")
        for path in directory.iterdir():
            if not re.fullmatch(re.escape(folder_name) + r"(?:-\d+)?\.json",
                                path.name):
                continue
            if not _safe(path, root):
                raise RuntimeError("ROLLING72_RECEIPT_UNSAFE")
            receipt = _json(path)
            if not receipt or receipt.get("run") != folder_name:
                raise RuntimeError("ROLLING72_RECEIPT_MISMATCH")
            freed += path.stat().st_size
            path.unlink()
    return freed


def _remove_pending(db, root, run_id, folder_name) -> int:
    path = root / "runs" / folder_name
    if not RUN_DIR.fullmatch(folder_name) or not _safe(path, root / "runs"):
        raise RuntimeError("ROLLING72_PENDING_PATH_INVALID")
    freed = 0
    if path.exists():
        if not _safe_tree(path, root / "runs"):
            raise RuntimeError("ROLLING72_PENDING_TREE_UNSAFE")
        # Never act on run dir recreated or reused under the same name.
        detail = _json(path / "deep_shadow.json")
        if not detail or detail.get("run_id") != run_id:
            raise RuntimeError("ROLLING72_PENDING_RUN_MISMATCH")
        for base, dirs, files in os.walk(path, followlinks=False):
            for name in files:
                freed += (Path(base) / name).stat().st_size
        shutil.rmtree(path)
    freed += _purge_auxiliary(root, run_id, folder_name)
    db.execute("DELETE FROM rolling72_pending WHERE run_id=?", (run_id,))
    db.commit()
    return freed


def cleanup(root: Path, *, apply=False, max_runs=MAX_PER_CYCLE) -> dict:
    root = Path(root).resolve()
    if not 1 <= max_runs <= 24:
        raise ValueError("ROLLING72_MAX_RUNS_1_TO_24")
    if not apply:
        return plan(root)
    _require_activation(root)
    # Scanner uses this same lock; no SQL writer can overlap this cleanup.
    with exclusive_lock(root / "v4-local-shadow.lock"):
        _require_activation(root)
        out = {"status": "NOT_NEEDED", "deleted": 0,
               "sqlite_modified": False, "raw_folders_deleted": 0,
               "reclaimed_bytes": 0, "blocked": 0}
        dbfile = root / "sqlite" / "v4-shadow.sqlite3"
        with closing(sqlite3.connect(dbfile, timeout=30)) as db:
            db.execute("PRAGMA busy_timeout=30000")
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("CREATE TABLE IF NOT EXISTS rolling72_pending ("
                       "run_id TEXT PRIMARY KEY,folder_name TEXT NOT NULL UNIQUE,"
                       "created_at TEXT NOT NULL)")
            db.commit()
            for run_id, folder_name in _pending(db):
                out["reclaimed_bytes"] += _remove_pending(db, root, run_id, folder_name)
                out["raw_folders_deleted"] += 1
            rows, warnings = _history(root, db)
            if warnings:
                return {**out, "status": "BLOCKED_HISTORY_INTEGRITY",
                        "warnings": warnings}
            if len(rows) <= KEEP:
                return out
            chosen = rows[KEEP:]
            for run_id, name, _, _, _ in reversed(chosen):
                if out["deleted"] >= max_runs:
                    break
                folder = root / "runs" / name
                if _mail_guards(root, folder) or not _safe_tree(folder, root / "runs"):
                    out["blocked"] += 1
                    continue
                # Never remove any row in the latest 72 success window.
                again, bad = _history(root, db)
                if bad or len(again) <= KEEP or (
                        run_id not in {row[0] for row in again[KEEP:]}):
                    raise RuntimeError("ROLLING72_WINDOW_CHANGED")
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute(
                        "INSERT INTO rolling72_pending VALUES (?,?,?)",
                        (run_id, name, datetime.now(timezone.utc).isoformat()))
                    db.execute("DELETE FROM proof_versions WHERE run_id=?", (run_id,))
                    if _table(db, "v4_cold_proofs"):
                        db.execute("DELETE FROM v4_cold_proofs WHERE run_id=?", (run_id,))
                    cursor = db.execute("DELETE FROM scan_runs WHERE run_id=?", (run_id,))
                    if cursor.rowcount != 1:
                        raise RuntimeError("ROLLING72_SCAN_ROW_MISSING")
                    db.commit()
                except BaseException:
                    db.rollback()
                    raise
                out["sqlite_modified"] = True
                out["deleted"] += 1
                out["reclaimed_bytes"] += _remove_pending(db, root, run_id, name)
                out["raw_folders_deleted"] += 1
            if out["deleted"]:
                out["status"] = "CLEANED"
                if db.execute("PRAGMA auto_vacuum").fetchone() == (2,):
                    # Bounded maintenance, only where incremental auto_vacuum exists.
                    db.execute("PRAGMA incremental_vacuum(1000)").fetchall()
                    db.commit()
        return out


def main():
    p = argparse.ArgumentParser(description="V4 72-run lifecycle; default READ ONLY")
    p.add_argument("--data-root", type=Path, default=Path.home() / "EVE-V4-Data")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--activate-with-backup", type=Path)
    group.add_argument("--apply", action="store_true")
    p.add_argument("--max-runs", type=int, default=MAX_PER_CYCLE)
    a = p.parse_args()
    if a.activate_with_backup:
        result = activate(a.data_root, backup=a.activate_with_backup)
    else:
        result = cleanup(a.data_root, apply=a.apply, max_runs=a.max_runs)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
