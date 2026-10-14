"""Run exactly one complete V4 shadow census, then persist audited local SQLite.

Requires --execute-shadow. No outbox or mail-sending code is imported. Produces
independent run folders and exclusive process lock to prevent overlapping jobs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from v4.local_store import persist


@contextmanager
def exclusive_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if platform.system() == "Windows":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("ANOTHER_V4_LOCAL_SCAN_RUNNING") from exc
        try:
            yield
        finally:
            handle.seek(0)
            if platform.system() == "Windows":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _hash(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return {"bytes": path.stat().st_size, "sha256": h.hexdigest()}


def _step(name: str, commands: list[str], run_dir: Path, cwd: Path):
    output = run_dir / (name + ".log")
    print(name + ": starting; log=" + str(output), flush=True)
    with output.open("w", encoding="utf-8") as log:
        proc = subprocess.run(commands, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                              timeout=80*60, check=False)
    if proc.returncode:
        raise RuntimeError(name + "_FAILED:" + str(proc.returncode) + "; see " + str(output))
    print(name + ": completed", flush=True)


def run(data_root: Path) -> dict:
    repo = Path(__file__).resolve().parent.parent
    root = Path(data_root).resolve()
    if root == repo or repo in root.parents:
        raise ValueError("DATA_ROOT_MUST_BE_OUTSIDE_REPOSITORY")
    with exclusive_lock(root / "v4-local-shadow.lock"):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = root / "runs" / (stamp + "-" + uuid.uuid4().hex[:8])
        run_dir.mkdir(parents=True, exist_ok=False)
        raw = run_dir / "source"
        report = run_dir / "full_market_report.json"
        deep = run_dir / "deep_shadow.json"
        proofs = run_dir / "all_proofs.jsonl"
        database = root / "sqlite" / "v4-shadow.sqlite3"
        manifest = run_dir / "manifest.json"
        common = [sys.executable, "-m"]
        progress = {"status":"STARTED", "run_folder":str(run_dir),
                    "mail_enabled":False, "persisted_to_cloudflare":False,
                    "started_at":datetime.now(timezone.utc).isoformat()}
        manifest.write_text(json.dumps(progress, indent=2), encoding="utf-8")
        try:
            _step("full_scan", common+["v4.full_scan","--data-dir",str(raw),
                                      "--output",str(report)],run_dir,repo)
            _step("deep_scan", common+["v4.deep_scan",
                                     "--market",str(raw / "market_orders.csv.bz2"),
                                     "--contracts",str(raw / "public_contracts.tar.bz2"),
                                     "--output",str(deep)],run_dir,repo)
            audit = persist(database, deep, proofs)
            full = json.loads(report.read_text(encoding="utf-8"))
            detail = json.loads(deep.read_text(encoding="utf-8"))
            coverage = detail.get("structure_health",{})
            lanes_failed = {k:v.get("reason") for k,v in coverage.items()
                            if v.get("status") != "COMPLETE"}
            result = {
                **progress, "status":"SHADOW_RECORDED",
                "full_census":full.get("overall"),
                "source_market_orders":full.get("market",{}).get("market_raw_rows"),
                "deep_public_orders":detail.get("public_market_orders"),
                "structure_health":coverage,
                "coverage_gate":"PARTIAL_UNVERIFIED" if lanes_failed or detail.get("source_input_integrity") != "ALL_PARSED"
                                else "INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
                "failed_structure_lanes":lanes_failed,
                "sqlite_unique_proofs":audit["sqlite_unique_proofs"],
                "proofs_sha256":audit["proofs_sha256"],
                "snapshot_hashes":{
                    "market_orders":_hash(raw/"market_orders.csv.bz2"),
                    "public_contracts":_hash(raw/"public_contracts.tar.bz2")},
                "shadow_audit":audit,
                "db_path":str(database),
                "finished_at":datetime.now(timezone.utc).isoformat(),
                "mail_enabled":False,
                "ready_for_production":False,
            }
        except Exception as exc:
            result = {**progress,"status":"FAILED","reason":type(exc).__name__+":"+str(exc),
                      "finished_at":datetime.now(timezone.utc).isoformat()}
            manifest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
            raise
        manifest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        return result


def main():
    p=argparse.ArgumentParser(description="Run one Windows V4 shadow scan without mail")
    p.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    p.add_argument("--execute-shadow",action="store_true",
                   help="Explicitly allow fresh EVE Ref/bridge network reads and local SQLite writes")
    args=p.parse_args()
    if not args.execute_shadow:
        p.error("refusing to scan without --execute-shadow")
    result=run(args.data_root)
    print(json.dumps({k:v for k,v in result.items() if k not in ("snapshot_hashes","structure_health","shadow_audit")},
                     ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
