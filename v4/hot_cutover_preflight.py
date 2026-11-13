"""Read-only preflight for a lossless V4 cold/hot candidate cutover.

This checker does not activate, move or delete any database file.
A candidate may be fresh only if every committed live scan_runs row agrees.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from v4.proof_cold_archive import ledger_runs

CHUNK=1024*1024


def _sha(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda:handle.read(CHUNK),b""):
            digest.update(block)
    return digest.hexdigest()


def preflight(root: Path, candidate: Path | None=None, *, verify_hash=False) -> dict:
    root=root.resolve()
    folder=root/"hot-stage"
    report={"status":"NOT_READY", "live_modified":False,
            "candidate_modified":False, "cutover_performed":False,
            "off_machine_backup_verified":False,
            "problems":[]}
    if not folder.is_dir() or folder.is_symlink():
        report["problems"].append("NO_SAFE_HOT_STAGE_DIRECTORY")
        return report
    if candidate is None:
        manifests=sorted(folder.glob("v4-shadow-hot-*.manifest.json"),
                         key=lambda p:p.name,reverse=True)
        if not manifests:
            report["problems"].append("NO_STAGE_MANIFEST")
            return report
        manifest_file=manifests[0]
        file=folder / manifest_file.name.replace(".manifest.json",".sqlite3")
    else:
        file=Path(candidate).resolve()
        manifest_file=file.with_name(file.name.replace(".sqlite3",".manifest.json"))
    if (folder not in file.parents or file.is_symlink()
            or not file.is_file() or manifest_file.is_symlink()
            or not manifest_file.is_file()):
        report["problems"].append("HOT_STAGE_PATH_INVALID")
        return report
    report["candidate"]=str(file)
    try:
        doc=json.loads(manifest_file.read_text(encoding="utf-8"))
    except (ValueError,OSError):
        report["problems"].append("STAGE_MANIFEST_UNREADABLE")
        return report
    if (doc.get("status")!="STAGED_NOT_ACTIVATED"
            or doc.get("safe_to_replace_live_automatically") is not False
            or doc.get("candidate_file")!=file.name
            or doc.get("candidate_bytes")!=file.stat().st_size
            or not doc.get("incremental_auto_vacuum")
            or doc.get("hot_policy_active") is not False):
        report["problems"].append("STAGE_MANIFEST_INVALID")
        return report
    if verify_hash and _sha(file)!=doc.get("candidate_sha256"):
        report["problems"].append("STAGE_CANDIDATE_SHA256_MISMATCH")
        return report
    active=ledger_runs(root)
    uri="file:"+file.resolve().as_posix()+"?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri,uri=True,timeout=30)) as db:
        if db.execute("PRAGMA auto_vacuum").fetchone()[0]!=2:
            report["problems"].append("STAGE_AUTO_VACUUM_NOT_INCREMENTAL")
            return report
        if not db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='v4_hot_policy'").fetchone():
            report["problems"].append("STAGE_NEEDS_REBUILD_FOR_NEW_HOT_POLICY")
            return report
        marker=db.execute(
            "SELECT policy_version,keep_runs,active FROM v4_hot_policy "
            "WHERE singleton=1").fetchone()
        if marker!=(1,doc.get("keep_runs"),0):
            report["problems"].append("STAGE_POLICY_MARKER_INVALID")
            return report
        retained=int(doc["keep_runs"])
        cand=[
            dict(zip(("run_id","status","proof_count",
                      "proof_sha256","audited_at"),r))
            for r in db.execute(
                "SELECT run_id,status,proof_count,proof_sha256,audited_at "
                "FROM scan_runs ORDER BY audited_at DESC,run_id DESC")]
        if cand!=active:
            report["problems"].append("STAGE_STALE_OR_LEDGER_METADATA_CHANGED")
            report["stage_runs"]=len(cand)
            report["live_runs"]=len(active)
            return report
        cold=active[retained:]
        if db.execute("SELECT COUNT(*) FROM v4_cold_proofs").fetchone()[0]!=len(cold):
            report["problems"].append("STAGE_COLD_INDEX_INCOMPLETE")
            return report
        count=0
        for row in active[:retained]:
            n=db.execute(
                "SELECT COUNT(*) FROM proof_versions WHERE run_id=?",
                (row["run_id"],)).fetchone()[0]
            if n!=row["proof_count"]:
                report["problems"].append("STAGE_HOT_PROOF_MISMATCH")
                return report
            count+=n
        # Every cold-only run must be indexed, with an immutable archive
        # manifest that agrees with the committed SQLite proof ledger.
        for row in cold:
            n=db.execute(
                "SELECT 1 FROM proof_versions WHERE run_id=? LIMIT 1",
                (row["run_id"],)).fetchone()
            ix=db.execute(
                "SELECT archive_sha256,raw_sha256,proof_count "
                "FROM v4_cold_proofs WHERE run_id=?",
                (row["run_id"],)).fetchone()
            archive=(root/"cold-proof-archives"/
                     (row["run_id"]+".jsonl.gz"))
            manifest=(root/"cold-proof-archives"/
                      (row["run_id"]+".manifest.json"))
            if n or not ix or not archive.is_file() or not manifest.is_file():
                report["problems"].append("STAGE_COLD_ARCHIVE_MISSING")
                return report
            payload=json.loads(manifest.read_text(encoding="utf-8"))
            if ix!=(payload.get("archive_sha256"),row["proof_sha256"],
                    row["proof_count"]) or payload.get("proof_sha256")!=row["proof_sha256"]:
                report["problems"].append("STAGE_COLD_ARCHIVE_METADATA_MISMATCH")
                return report
        if count!=doc.get("hot_proof_rows") or len(cold)!=doc.get("cold_verified_runs"):
            report["problems"].append("STAGE_MANIFEST_TOTALS_MISMATCH")
            return report
    report.update({
        "status":"CANDIDATE_READY_FOR_CONTROLLED_MAINTENANCE",
        "live_scan_runs":len(active),
        "hot_runs":min(len(active),doc["keep_runs"]),
        "hot_proof_rows":count,
        "cold_archived_runs":len(active)-min(len(active),doc["keep_runs"]),
        "candidate_gib":round(file.stat().st_size/(1024**3),3),
        "candidate_hash_rechecked":verify_hash,
        "requires_shadow_task_paused":True,
        "requires_off_machine_backup":True,
        "production_switch_not_implemented_here":True,
    })
    return report


def main():
    p=argparse.ArgumentParser(description="V4 read-only hot-stage preflight")
    p.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    p.add_argument("--candidate",type=Path)
    p.add_argument("--verify-hash",action="store_true",
                   help="Read entire candidate and compare against sealed sha256")
    args=p.parse_args()
    status=preflight(args.data_root,candidate=args.candidate,
                     verify_hash=args.verify_hash)
    print(json.dumps(status,ensure_ascii=False,indent=2))
    if status["status"]!="CANDIDATE_READY_FOR_CONTROLLED_MAINTENANCE":
        raise SystemExit(2)


if __name__=="__main__":
    main()
