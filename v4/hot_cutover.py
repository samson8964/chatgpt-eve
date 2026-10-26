"""Guarded Windows V4 cold/hot cutover.

Default is PREVIEW (read-only). Applying is refused unless both scheduled
jobs are DISABLED, a verified CURRENT backup exists on a DIFFERENT volume,
the entire candidate/archival preflight passes, the V4 process lock is free,
and explicit operator acknowledgment is supplied.

An apply preserves the original complete database in a rollback directory,
copies/stamps the isolated candidate and promotes it with an immediate
integrity check. It NEVER erases the old DB or any archival/run artifact.
"""
from __future__ import annotations

import argparse
import json
import locale
import os
import platform
import shutil
import sqlite3
import subprocess
import uuid
import xml.etree.ElementTree as ET
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from v4.hot_cutover_preflight import preflight
from v4.local_run import exclusive_lock
from v4.proof_cold_archive import ledger_runs

TASKS = ("EVE-V4-Shadow", "EVE-V4-Opportunity-Push")
ACK = "I_ACCEPT_V4_HOT_CUTOVER"
GIB = 1024**3


def _parse_task_xml(data: bytes) -> ET.Element:
    """Interpret schtasks stdout despite its often incorrect XML encoding.

    Some localized Windows versions emit UTF-8 or console/OEM code-page
    *bytes* with an XML header claiming UTF-16. Passing those raw bytes
    to ElementTree raises "encoding specified in XML declaration is
    incorrect" even though the XML definition is otherwise well-formed.
    Decode to Unicode and let ElementTree parse the resulting str.
    """
    if not data or len(data) > 8 * 1024 * 1024:
        raise ValueError("TASK_XML_OUTPUT_EMPTY_OR_OVERSIZE")
    candidates = ["utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"]
    try:
        console = locale.getencoding()
        if console:
            candidates.append(console)
    except (AttributeError, ValueError):
        pass
    # schtasks commonly returns an OEM-codepage representation on
    # Chinese Windows even when Python was launched in UTF-8 mode.
    candidates.extend(["mbcs", "cp936", "cp950", "cp932"])
    try:
        direct = ET.fromstring(data)
        if direct.tag.split("}")[-1] == "Task":
            return direct
    except ET.ParseError:
        pass
    for encoding in dict.fromkeys(candidates):
        try:
            decoded = data.decode(encoding, errors="strict")
            node = ET.fromstring(decoded)
            if node.tag.split("}")[-1] == "Task":
                return node
        except (UnicodeError, LookupError, ET.ParseError):
            continue
    raise ValueError("TASK_XML_DECODE_OR_STRUCTURE_INVALID")


def _task_disabled(task: str) -> bool:
    """Check overall Task Settings.Enabled without localized status text."""
    call=subprocess.run(
        ["schtasks.exe","/Query","/TN",task,"/XML"],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,
        timeout=15)
    if call.returncode!=0:
        raise RuntimeError("SCHEDULED_TASK_NOT_READABLE:"+task)
    try:
        root=_parse_task_xml(call.stdout)
    except ValueError as exc:
        raise RuntimeError("SCHEDULED_TASK_XML_INVALID:"+task) from exc
    # Trigger <Enabled> can differ from overall task <Settings><Enabled>.
    # Never mistake a disabled trigger for a disabled scheduled task.
    settings = next(
        (node for node in root.iter()
         if node.tag.split("}")[-1] == "Settings"), None)
    if settings is None:
        return False
    enabled = next(
        (node for node in settings
         if node.tag.split("}")[-1] == "Enabled"), None)
    # Missing/unknown Enabled is never accepted as proof of DISABLED.
    return (enabled is not None
            and (enabled.text or "").strip().lower() == "false")


def _db_connection(path: Path):
    # Backup and stage files must be closed, self-contained SQLite copies.
    return sqlite3.connect(
        "file:"+path.resolve().as_posix()+"?mode=ro&immutable=1",
        uri=True,timeout=30)


def _verified_independent_backup(root: Path, backup: Path) -> dict:
    if not backup or not backup.is_file() or backup.is_symlink():
        raise RuntimeError("EXTERNAL_BACKUP_FILE_REQUIRED")
    backup=backup.resolve()
    if root==backup or root in backup.parents:
        raise RuntimeError("EXTERNAL_BACKUP_MUST_BE_OUTSIDE_DATA_ROOT")
    if platform.system()=="Windows":
        if not backup.drive or backup.drive.lower()==root.drive.lower():
            raise RuntimeError("EXTERNAL_BACKUP_MUST_BE_ON_OTHER_VOLUME")
    if backup.stat().st_size < 1024:
        raise RuntimeError("EXTERNAL_BACKUP_TOO_SMALL")
    live=ledger_runs(root)
    live_db=root/"sqlite"/"v4-shadow.sqlite3"
    # Read the LOGICAL live database including committed WAL frames.
    # immutable=1 skips WAL and may falsely report a healthy full backup as
    # stale during the pre-checkpoint maintenance phase. Promotion still
    # requires _no_uncheckpointed_sidecars(live) before any rename.
    with closing(sqlite3.connect(
            "file:"+live_db.resolve().as_posix()+"?mode=ro",
            uri=True,timeout=30)) as source_db:
        live_proofs=source_db.execute(
            "SELECT COUNT(*) FROM proof_versions").fetchone()[0]
        live_policy=source_db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='v4_hot_policy'").fetchone()
    if live_policy:
        raise RuntimeError("SOURCE_ALREADY_CONTAINS_HOT_POLICY")
    if live_proofs!=sum(r["proof_count"] for r in live):
        raise RuntimeError("SOURCE_FULL_HISTORICAL_PROOFS_REQUIRED")
    with closing(_db_connection(backup)) as db:
        try:
            check=db.execute("PRAGMA integrity_check").fetchone()[0]
            runs=db.execute(
                "SELECT run_id,status,proof_count,proof_sha256,audited_at "
                "FROM scan_runs ORDER BY audited_at DESC,run_id DESC").fetchall()
            proofs=db.execute(
                "SELECT COUNT(*) FROM proof_versions").fetchone()[0]
        except sqlite3.DatabaseError as exc:
            raise RuntimeError("EXTERNAL_BACKUP_NOT_VALID_SQLITE") from exc
    keys=("run_id","status","proof_count","proof_sha256","audited_at")
    if check!="ok" or [dict(zip(keys,row)) for row in runs]!=live:
        raise RuntimeError("EXTERNAL_BACKUP_INVALID_OR_STALE")
    if proofs!=live_proofs:
        raise RuntimeError("EXTERNAL_BACKUP_PROOF_COUNT_INCONSISTENT")
    return {"status":"VERIFIED_CURRENT_SEPARATE_VOLUME",
            "path":str(backup),"scan_runs":len(runs),
            "proof_rows":proofs,"sqlite_integrity":"ok"}


def _no_uncheckpointed_sidecars(path: Path) -> None:
    if any(path.with_name(path.name + suffix).exists()
           for suffix in ("-wal","-shm","-journal")):
        raise RuntimeError("SQLITE_JOURNAL_PRESENT_CLOSE_ALL_V4_READERS")


def _fresh_candidate(root: Path, candidate: Path | None) -> dict:
    decision=preflight(root,candidate=candidate,verify_hash=True)
    if decision["status"]!="CANDIDATE_READY_FOR_CONTROLLED_MAINTENANCE":
        raise RuntimeError(
            "STAGED_CANDIDATE_NOT_READY:"+",".join(decision["problems"]))
    return decision


def inspect(root: Path, *, candidate: Path | None=None) -> dict:
    root=root.resolve()
    decision=preflight(root,candidate=candidate,verify_hash=False)
    tasks={}
    if platform.system()=="Windows":
        for task in TASKS:
            try:
                tasks[task]="DISABLED" if _task_disabled(task) else "ENABLED"
            except RuntimeError as exc:
                tasks[task]=str(exc)
    else:
        tasks={task:"NOT_WINDOWS" for task in TASKS}
    return {
        "status":"READ_ONLY_CUTOVER_INSPECTION",
        "candidate":decision,
        "scheduled_tasks":tasks,
        "live_database_modified":False,
        "formal_push_modified":False,
        "off_machine_backup_verified":False,
        "cutover_performed":False,
        "requires_verified_external_backup":True,
    }


def _check_tasks_disabled() -> None:
    if platform.system()!="Windows":
        raise RuntimeError("PRODUCTION_CUTOVER_WINDOWS_ONLY")
    for name in TASKS:
        if not _task_disabled(name):
            raise RuntimeError("DISABLE_SCHEDULED_TASK_BEFORE_CUTOVER:"+name)


def _promote(root: Path, candidate: Path, backup: Path) -> dict:
    live=root/"sqlite"/"v4-shadow.sqlite3"
    if not live.is_file() or live.is_symlink():
        raise RuntimeError("ACTIVE_LEDGER_MISSING_OR_UNSAFE")
    _no_uncheckpointed_sidecars(live)
    verified=_verified_independent_backup(root,backup)
    _fresh_candidate(root,candidate)
    staged=candidate.resolve()
    if not staged.is_file() or staged.is_symlink():
        raise RuntimeError("STAGE_CANDIDATE_MISSING")
    _no_uncheckpointed_sidecars(staged)
    free=shutil.disk_usage(root).free
    if free < staged.stat().st_size + 10*GIB:
        raise RuntimeError("INSUFFICIENT_SPACE_FOR_ACTIVATION_COPY")
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    token=stamp+"-"+uuid.uuid4().hex[:8]
    rollback_dir=root/"hot-cutover-rollback"
    rollback_dir.mkdir(parents=True,exist_ok=True)
    if rollback_dir.is_symlink():
        raise RuntimeError("UNSAFE_ROLLBACK_DIR")
    old=rollback_dir/("v4-shadow-before-"+token+".sqlite3")
    failed=rollback_dir/("v4-shadow-failed-"+token+".sqlite3")
    temporary=live.with_name("v4-shadow-cutover-"+token+".sqlite3.part")
    if any(p.exists() for p in (old,failed,temporary)):
        raise RuntimeError("CUTOVER_OUTPUT_ALREADY_EXISTS")

    original_moved=False
    new_installed=False
    try:
        # Never modify sealed hot-stage candidate or its manifest.
        shutil.copyfile(staged,temporary)
        with closing(sqlite3.connect(temporary,timeout=30)) as db:
            db.execute("PRAGMA busy_timeout=30000")
            db.execute("BEGIN IMMEDIATE")
            marker=db.execute(
                "SELECT policy_version,keep_runs,active FROM v4_hot_policy "
                "WHERE singleton=1").fetchone()
            if not marker or marker[0]!=1 or marker[1]<24 or marker[2]!=0:
                raise RuntimeError("STAGED_POLICY_UNSAFE")
            db.execute("UPDATE v4_hot_policy SET active=1 WHERE singleton=1")
            db.commit()
            if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise RuntimeError("ACTIVATED_COPY_INTEGRITY_FAILED")
            if db.execute("PRAGMA auto_vacuum").fetchone()[0]!=2:
                raise RuntimeError("ACTIVATED_COPY_VACUUM_MODE_INCORRECT")
        _no_uncheckpointed_sidecars(temporary)
        # Candidate and old ledger freshness are rechecked directly
        # before swapping, while the V4 single-process lock is held.
        _check_tasks_disabled()
        _fresh_candidate(root,staged)
        _no_uncheckpointed_sidecars(live)
        os.replace(live,old)
        original_moved=True
        os.replace(temporary,live)
        new_installed=True
        with closing(_db_connection(live)) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise RuntimeError("PROMOTED_HOT_INTEGRITY_FAILED")
            if db.execute(
                    "SELECT active FROM v4_hot_policy WHERE singleton=1").fetchone()!=(1,):
                raise RuntimeError("PROMOTED_POLICY_NOT_ACTIVE")
        return {"status":"ACTIVATED_NEEDS_OPERATOR_REENABLE_TASKS",
                "original_rollback_file":str(old),
                "active_database":str(live),
                "source_backup":verified,
                "original_database_preserved":True,
                "formal_push_task_unchanged":True,
                "recovery_test_still_required":True}
    except BaseException:
        if original_moved:
            # Immediate rollback is safe only BEFORE task re-enable, as
            # protected by the exclusive V4 scanner/push process lock.
            if new_installed and live.exists():
                os.replace(live,failed)
            if not live.exists():
                os.replace(old,live)
        raise
    finally:
        temporary.unlink(missing_ok=True)


def activate(root: Path, *, candidate: Path, external_backup: Path,
             acknowledgement: str) -> dict:
    if acknowledgement!=ACK:
        raise RuntimeError("OPERATOR_EXPLICIT_ACK_REQUIRED")
    root=root.resolve()
    _check_tasks_disabled()
    with exclusive_lock(root/"v4-local-shadow.lock"):
        _check_tasks_disabled()
        return _promote(root,candidate,external_backup)


def main():
    parser=argparse.ArgumentParser(description="V4 guarded cold/hot cutover")
    parser.add_argument("--data-root",type=Path,
                        default=Path.home()/"EVE-V4-Data")
    parser.add_argument("--candidate",type=Path)
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--external-backup",type=Path)
    parser.add_argument("--ack",default="")
    args=parser.parse_args()
    if args.apply:
        if args.candidate is None or args.external_backup is None:
            parser.error("--apply needs --candidate and --external-backup")
        outcome=activate(args.data_root,candidate=args.candidate,
                         external_backup=args.external_backup,
                         acknowledgement=args.ack)
    else:
        outcome=inspect(args.data_root,candidate=args.candidate)
    print(json.dumps(outcome,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
