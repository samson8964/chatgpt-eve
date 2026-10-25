"""Build a smaller *offline candidate* V4 shadow ledger. Never activate/delete live data.

Run this only after losslessly archiving and verifying EVERY old proof run.
This module copies all scan_runs metadata and only latest N proof_versions.
Production remains unchanged: no scheduler, notifier, live DB replace or prune.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from v4.local_store import _init
from v4.proof_cold_archive import KEEP_RUNS, ledger_runs, verify_archive

MIN_FREE_GIB = 35
BATCH = 3000


def preview(root: Path, keep_runs: int = KEEP_RUNS) -> dict:
    root = root.resolve()
    if keep_runs < 24:
        raise ValueError("HOT_KEEP_RUNS_MUST_BE_AT_LEAST_24")
    rows = ledger_runs(root)
    old = rows[keep_runs:]
    archive_dir = root / "cold-proof-archives"
    missing = [r["run_id"] for r in old
               if not (archive_dir / (r["run_id"] + ".manifest.json")).is_file()
               or not (archive_dir / (r["run_id"] + ".jsonl.gz")).is_file()]
    return {
        "status": "READ_ONLY_HOT_STAGE_PREVIEW",
        "source_runs": len(rows),
        "hot_run_target": min(keep_runs,len(rows)),
        "cold_run_target": len(old),
        "missing_archives": len(missing),
        "missing_archive_samples": missing[:10],
        "can_stage": not missing and bool(old),
        "live_database_untouched": True,
    }


def _read_runs(db: sqlite3.Connection) -> list[dict]:
    return [dict(zip(("run_id","status","proof_count",
                      "proof_sha256","audited_at"), row))
            for row in db.execute(
                "SELECT run_id,status,proof_count,proof_sha256,audited_at "
                "FROM scan_runs ORDER BY audited_at DESC,run_id DESC")]


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def stage(root: Path, *, keep_runs=KEEP_RUNS) -> dict:
    root=root.resolve()
    plan=preview(root,keep_runs=keep_runs)
    if not plan["can_stage"]:
        raise RuntimeError("OLD_RUN_COLD_ARCHIVES_NOT_COMPLETE")
    if shutil.disk_usage(root).free < MIN_FREE_GIB*(1024**3):
        raise RuntimeError("INSUFFICIENT_DISK_FOR_HOT_STAGE")
    before=ledger_runs(root)
    old=before[keep_runs:]
    for n, record in enumerate(old, start=1):
        if record["status"] != "SHADOW_VERIFIED_OFFLINE":
            raise RuntimeError("OLD_RUN_NOT_VERIFIED")
        verify_archive(root,record)
        if n % 10 == 0 or n == len(old):
            print("COLD_COVERAGE_VERIFIED",n,"of",len(old),flush=True)
    live=root/"sqlite"/"v4-shadow.sqlite3"
    output_dir=root/"hot-stage"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name=f"v4-shadow-hot-{stamp}-{os.getpid()}"
    candidate=output_dir/(name+".sqlite3")
    manifest=output_dir/(name+".manifest.json")
    # Candidate is never promoted to the active DB in this function.
    if candidate.exists() or manifest.exists():
        raise FileExistsError("HOT_STAGE_ALREADY_EXISTS")
    partial=candidate.with_name(candidate.name+".part")
    try:
        uri="file:"+live.resolve().as_posix()+"?mode=ro"
        with closing(sqlite3.connect(uri,uri=True,timeout=30)) as source:
            source.execute("BEGIN")
            current=_read_runs(source)
            # Fail closed if a scan completed while cold coverage was checked.
            if current != before:
                raise RuntimeError("LIVE_RUN_SET_CHANGED_RETRY_PREPARATION")
            retained=current[:keep_runs]
            with closing(sqlite3.connect(partial,timeout=30)) as dest:
                _init(dest)
                dest.execute("PRAGMA foreign_keys=ON")
                for row in source.execute(
                    "SELECT run_id,status,proof_count,proof_sha256,"
                    "report_json,audited_at FROM scan_runs"):
                    dest.execute("INSERT INTO scan_runs VALUES (?,?,?,?,?,?)",row)
                copied=0
                for i,rec in enumerate(retained,start=1):
                    count=0
                    cursor=source.execute(
                        "SELECT run_id,instance,status,reason,proof_json "
                        "FROM proof_versions WHERE run_id=?", (rec["run_id"],))
                    while True:
                        batch=cursor.fetchmany(BATCH)
                        if not batch:
                            break
                        dest.executemany(
                            "INSERT INTO proof_versions VALUES (?,?,?,?,?)",
                            batch)
                        count+=len(batch)
                    if count != rec["proof_count"]:
                        raise RuntimeError("HOT_RUN_PROOF_COUNT_MISMATCH:"+rec["run_id"])
                    copied+=count
                    if i%10==0 or i==len(retained):
                        print("HOT_RUN_COPIED",i,"of",len(retained),
                              "proof_rows",copied,flush=True)
                dest.commit()
                actual=dest.execute(
                    "SELECT COUNT(*) FROM proof_versions").fetchone()[0]
                runs=dest.execute("SELECT COUNT(*) FROM scan_runs").fetchone()[0]
                if actual!=copied or runs!=len(current):
                    raise RuntimeError("HOT_STAGE_TOTALS_MISMATCH")
                if dest.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                    raise RuntimeError("HOT_STAGE_INTEGRITY_FAILED")
                # Finalize as a self-contained, non-WAL artifact.
                dest.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                mode=dest.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
                if mode.lower()!="delete":
                    raise RuntimeError("HOT_STAGE_NOT_SELF_CONTAINED")
            source.rollback()
        if not partial.is_file():
            raise RuntimeError("HOT_STAGE_OUTPUT_MISSING")
        # Fail before promotion if any leftover WAL contains required pages.
        if (partial.with_name(partial.name+"-wal")).exists():
            raise RuntimeError("HOT_STAGE_HAS_UNCHECKPOINTED_WAL")
        os.replace(partial,candidate)
        meta={
            "format":"V4_HOT_STAGE_OFFLINE_V1",
            "status":"STAGED_NOT_ACTIVATED",
            "keep_runs":keep_runs,
            "source_runs":len(current),
            "cold_verified_runs":len(old),
            "hot_proof_rows":copied,
            "source_latest_run":current[0]["run_id"],
            "source_latest_audited_at":current[0]["audited_at"],
            "candidate_file":candidate.name,
            "candidate_sha256":_sha(candidate),
            "candidate_bytes":candidate.stat().st_size,
            "live_database_untouched":True,
            "safe_to_replace_live_automatically":False,
            "off_machine_backup_required":True,
        }
        temp_manifest=manifest.with_name(manifest.name+".part")
        with temp_manifest.open("x",encoding="utf-8") as stream:
            json.dump(meta,stream,ensure_ascii=False,indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_manifest,manifest)
        return {"status":"STAGED_NOT_ACTIVATED",
                "candidate_db":str(candidate),
                "manifest":str(manifest),
                "source_runs":len(current),
                "cold_verified_runs":len(old),
                "hot_runs":len(retained),
                "hot_proof_rows":copied,
                "candidate_gib":round(candidate.stat().st_size/(1024**3),3),
                "live_database_modified":False}
    finally:
        partial.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description="V4 reversible hot ledger stage")
    parser.add_argument("--data-root",type=Path,
                        default=Path.home()/"EVE-V4-Data")
    parser.add_argument("--keep-runs",type=int,default=KEEP_RUNS)
    parser.add_argument("--stage",action="store_true",
                        help="Build offline compact candidate ONLY; NEVER activate")
    args=parser.parse_args()
    result=(stage(args.data_root,keep_runs=args.keep_runs)
            if args.stage else preview(args.data_root,keep_runs=args.keep_runs))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
