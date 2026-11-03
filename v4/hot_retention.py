"""V4 bounded SQLite hot proof retention.

Fails CLOSED unless a carefully staged ledger has been explicitly activated
(policy singleton active=1 and SQLite auto_vacuum=INCREMENTAL).
For each aging run, verify its lossless gzip archive and raw checksum BEFORE
deleting duplicate SQLite proof rows. Never deletes original run files.
No mail or ESI operations; no scheduled task changes.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from v4.local_run import exclusive_lock
from v4.proof_cold_archive import (
    archive_one, ledger_runs, source_index, verify_archive, _archive_paths,
)

DEFAULT_MAX_RUNS = 1
MAX_VACUUM_PAGES = 25000
MAX_VACUUM_SECONDS = 20


def _reclaim_free_pages(db: sqlite3.Connection, *, limit: int,
                        seconds: float = MAX_VACUUM_SECONDS) -> dict:
    """Bounded incremental vacuum; trust observed pages, not PRAGMA(N) intent.

    SQLite is allowed to release fewer than N pages on one invocation.
    On some builds, a single cursor produces only one successful step.
    Retry while there is *measured* progress, with both page and time caps.
    """
    before_free = int(db.execute("PRAGMA freelist_count").fetchone()[0])
    before_pages = int(db.execute("PRAGMA page_count").fetchone()[0])
    after_free, after_pages = before_free, before_pages
    passes = 0
    deadline = time.monotonic() + seconds
    capped = min(before_free, limit)
    while (limit > 0 and before_free - after_free < capped
           and after_free > 0 and time.monotonic() < deadline):
        remaining = capped - (before_free - after_free)
        previous_free, previous_pages = after_free, after_pages
        cursor = db.execute(f"PRAGMA incremental_vacuum({remaining})")
        try:
            # Complete every SQLite step. Cursor construction alone is
            # insufficient on some Python/SQLite combinations.
            for _ in cursor:
                pass
        finally:
            cursor.close()
        passes += 1
        after_free = int(db.execute("PRAGMA freelist_count").fetchone()[0])
        after_pages = int(db.execute("PRAGMA page_count").fetchone()[0])
        if after_free >= previous_free and after_pages >= previous_pages:
            break  # No forward progress: fail closed, never loop forever.
    reclaimed = max(0, before_pages - after_pages)
    return {
        "vacuum_freelist_before": before_free,
        "vacuum_freelist_after": after_free,
        "vacuum_page_count_before": before_pages,
        "vacuum_page_count_after": after_pages,
        "vacuum_passes": passes,
        "vacuum_pages_reclaimed": reclaimed,
        "vacuum_incomplete": after_free > max(0, before_free - limit),
    }


def policy(root: Path) -> dict:
    db_file = root / "sqlite" / "v4-shadow.sqlite3"
    if not db_file.is_file():
        return {"status":"NO_LEDGER","enabled":False}
    uri = "file:" + db_file.resolve().as_posix() + "?mode=ro"
    with closing(sqlite3.connect(uri,uri=True,timeout=30)) as db:
        present = db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='v4_hot_policy'").fetchone()
        if not present:
            return {"status":"NOT_CONFIGURED","enabled":False}
        row = db.execute(
            "SELECT policy_version,keep_runs,active FROM v4_hot_policy "
            "WHERE singleton=1").fetchone()
        auto = db.execute("PRAGMA auto_vacuum").fetchone()[0]
        cold_table=db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='v4_cold_proofs'").fetchone()
        if not row or row[0]!=1 or row[1]<24 or auto!=2 or not cold_table:
            return {"status":"POLICY_INVALID","enabled":False}
        return {"status":"ACTIVE" if row[2]==1 else "STAGED_INACTIVE",
                "enabled":row[2]==1, "keep_runs":row[1],
                "incremental_auto_vacuum":True}


def maintain(root: Path, *, apply=False, max_runs=DEFAULT_MAX_RUNS,
             max_vacuum_pages=MAX_VACUUM_PAGES) -> dict:
    root=Path(root).resolve()
    if not 1 <= max_runs <= 3:
        raise ValueError("MAX_RUNS_BETWEEN_1_AND_3")
    if not 0 <= max_vacuum_pages <= 100000:
        raise ValueError("INVALID_VACUUM_PAGE_LIMIT")
    initial = policy(root)
    result = {
        "status":"READ_ONLY_HOT_RETENTION" if not apply else "NOT_ENABLED",
        "policy":initial, "eligible_old_runs":0,
        "runs_pruned":0,"proof_rows_pruned":0,
        "archived_new_runs":0,"vacuum_pages_reclaimed":0,
        "vacuum_freelist_before":0,"vacuum_freelist_after":0,
        "vacuum_page_count_before":0,"vacuum_page_count_after":0,
        "vacuum_passes":0,"vacuum_incomplete":False,
        "sqlite_modified":False,"original_runs_deleted":False,
        "error":None,
    }
    if not initial["enabled"]:
        result["status"]="NOT_ENABLED"
        return result

    # Same process lock used for the normal shadow scanner prevents a
    # competing scan append or another retention worker during mutation.
    with exclusive_lock(root/"v4-local-shadow.lock"):
        state=policy(root)
        if not state["enabled"] or state!=initial:
            raise RuntimeError("HOT_RETENTION_POLICY_CHANGED")
        history=ledger_runs(root)
        older=history[state["keep_runs"]:]
        db_file=root/"sqlite"/"v4-shadow.sqlite3"
        if not older:
            result["status"]="NOT_NEEDED" if apply else "READ_ONLY_HOT_RETENTION"
            return result
        with closing(sqlite3.connect(
                "file:"+db_file.resolve().as_posix()+"?mode=ro",uri=True)) as db:
            eligible=[
                row for row in older
                if db.execute(
                    "SELECT 1 FROM proof_versions WHERE run_id=? LIMIT 1",
                    (row["run_id"],)).fetchone()
            ]
        result["eligible_old_runs"]=len(eligible)
        if not apply:
            return result
        sources=source_index(root)
        for row in list(reversed(eligible))[:max_runs]:
            if row["status"]!="SHADOW_VERIFIED_OFFLINE":
                raise RuntimeError("UNVERIFIED_AGED_HOT_RUN")
            gzip_path,manifest_file=_archive_paths(root,row["run_id"])
            if gzip_path.exists() or manifest_file.exists():
                verify_archive(root,row)
            else:
                raw=sources.get(row["run_id"])
                if raw is None:
                    raise RuntimeError("MISSING_AGED_RAW_SOURCE")
                info=archive_one(root,row,raw)
                if info["status"]!="ARCHIVED_VERIFIED":
                    raise RuntimeError("COLD_ARCHIVE_NOT_VERIFIED")
                result["archived_new_runs"]+=1
            # Archive must remain valid prior to each destructive SQLite
            # statement, including sha-verified gzip decompression.
            verified=verify_archive(root,row)
            manifest=json.loads(manifest_file.read_text(encoding="utf-8"))
            with closing(sqlite3.connect(db_file,timeout=30)) as db:
                db.execute("PRAGMA foreign_keys=ON")
                if db.execute("PRAGMA auto_vacuum").fetchone()[0]!=2:
                    raise RuntimeError("INCREMENTAL_VACUUM_NOT_ENABLED")
                db.execute("BEGIN IMMEDIATE")
                try:
                    marker=db.execute(
                        "SELECT policy_version,keep_runs,active FROM "
                        "v4_hot_policy WHERE singleton=1").fetchone()
                    if marker!=(1,state["keep_runs"],1):
                        raise RuntimeError("RETENTION_POLICY_CHANGED_IN_TRANSACTION")
                    latest=[
                        r[0] for r in db.execute(
                            "SELECT run_id FROM scan_runs "
                            "ORDER BY audited_at DESC,run_id DESC "
                            "LIMIT ?",(state["keep_runs"],))]
                    if row["run_id"] in latest:
                        raise RuntimeError("AGED_RUN_ENTERED_HOT_WINDOW")
                    check=db.execute(
                        "SELECT status,proof_count,proof_sha256 "
                        "FROM scan_runs WHERE run_id=?", (row["run_id"],)).fetchone()
                    if check!=(row["status"],row["proof_count"],row["proof_sha256"]):
                        raise RuntimeError("AGED_RUN_METADATA_CHANGED")
                    db.execute(
                        "INSERT OR IGNORE INTO v4_cold_proofs "
                        "(run_id,archive_sha256,raw_sha256,proof_count,archived_at)"
                        " VALUES (?,?,?,?,?)",
                        (row["run_id"],manifest["archive_sha256"],
                         row["proof_sha256"],row["proof_count"],
                         datetime.now(timezone.utc).isoformat()))
                    indexed=db.execute(
                        "SELECT archive_sha256,raw_sha256,proof_count "
                        "FROM v4_cold_proofs WHERE run_id=?",(row["run_id"],)).fetchone()
                    if indexed!=(manifest["archive_sha256"],
                                 row["proof_sha256"],row["proof_count"]):
                        raise RuntimeError("COLD_INDEX_CONFLICT")
                    cursor=db.execute(
                        "DELETE FROM proof_versions WHERE run_id=?",
                        (row["run_id"],))
                    if cursor.rowcount!=verified["proof_count"]:
                        raise RuntimeError("PRUNED_ROW_COUNT_MISMATCH")
                    db.commit()
                except BaseException:
                    db.rollback()
                    raise
                result["runs_pruned"]+=1
                result["proof_rows_pruned"]+=cursor.rowcount
                result["sqlite_modified"]=True
                if max_vacuum_pages:
                    # Capture actual reduction in SQLite's logical file pages.
                    # Some SQLite builds reclaim fewer than requested pages
                    # per invocation, so use bounded, observable retries.
                    stats=_reclaim_free_pages(db,limit=max_vacuum_pages)
                    result["vacuum_pages_reclaimed"]+=stats["vacuum_pages_reclaimed"]
                    result["vacuum_freelist_before"]+=stats["vacuum_freelist_before"]
                    result["vacuum_freelist_after"]+=stats["vacuum_freelist_after"]
                    result["vacuum_page_count_before"]=stats["vacuum_page_count_before"]
                    result["vacuum_page_count_after"]=stats["vacuum_page_count_after"]
                    result["vacuum_passes"]+=stats["vacuum_passes"]
                    result["vacuum_incomplete"] |= stats["vacuum_incomplete"]
            print("HOT_RUN_ARCHIVED_PRUNED",row["run_id"],
                  "proof_rows",cursor.rowcount,flush=True)
        result["status"]="PRUNED" if result["runs_pruned"] else "NOT_NEEDED"
        return result


def main():
    parser=argparse.ArgumentParser(
        description="V4 HOT proof retention - disabled until staged DB activation")
    parser.add_argument("--data-root",type=Path,
                        default=Path.home()/"EVE-V4-Data")
    parser.add_argument("--apply",action="store_true",
                        help="Archive + prune at most 1 expired run, only if activated")
    parser.add_argument("--max-runs",type=int,default=DEFAULT_MAX_RUNS)
    args=parser.parse_args()
    result=maintain(args.data_root,apply=args.apply,
                    max_runs=args.max_runs)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
