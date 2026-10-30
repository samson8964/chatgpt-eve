"""Safe online SQLite backup of local V4 shadow ledger; never sends mail."""
from __future__ import annotations
import argparse
import json
import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def backup(data_root: Path) -> dict:
    root=Path(data_root).resolve()
    source=root/"sqlite"/"v4-shadow.sqlite3"
    if not source.is_file():
        raise FileNotFoundError("NO_LOCAL_SHADOW_SQLITE")
    folder=root/"backups"
    folder.mkdir(parents=True,exist_ok=True)
    destination=folder/("v4-shadow-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+".sqlite3")
    # Never publish a partially written backup with the final *.sqlite3
    # name: the scheduler's backup_due() must only see verified copies.
    partial=destination.with_name(destination.name+".part")
    if destination.exists() or partial.exists():
        raise FileExistsError("BACKUP_TARGET_EXISTS")
    try:
        with closing(sqlite3.connect(f"file:{source.as_posix()}?mode=ro",uri=True)) as original:
            with closing(sqlite3.connect(partial)) as target:
                start=time.monotonic()
                last=[start-60]
                def on_copy(_status, remaining, total):
                    tick=time.monotonic()
                    if tick-last[0]>=30 or remaining==0:
                        percent=round((total-remaining)*100/total,1) if total else 100
                        print("DAILY_BACKUP_COPY_PROGRESS",str(percent)+"%",
                              "elapsed_seconds",int(tick-start),flush=True)
                        last[0]=tick
                print("DAILY_BACKUP_COPY_START", source.stat().st_size, "bytes",flush=True)
                original.backup(target,pages=2048,sleep=0.1,progress=on_copy)
                print("DAILY_BACKUP_INTEGRITY_START",flush=True)
                integrity_start=time.monotonic()
                last_integrity=[integrity_start-60]
                callbacks=[0]
                def on_integrity():
                    callbacks[0]+=1
                    tick=time.monotonic()
                    if tick-last_integrity[0]>=60:
                        print("DAILY_BACKUP_INTEGRITY_ACTIVE",
                              "elapsed_seconds",int(tick-integrity_start),
                              "vm_callback_count",callbacks[0],flush=True)
                        last_integrity[0]=tick
                    return 0
                target.set_progress_handler(on_integrity,100000)
                try:
                    result=target.execute("PRAGMA integrity_check").fetchone()[0]
                finally:
                    target.set_progress_handler(None,0)
                if result!="ok":
                    raise RuntimeError("BACKUP_INTEGRITY_FAILED:"+str(result))
                print("DAILY_BACKUP_INTEGRITY_OK",
                      "elapsed_seconds",int(time.monotonic()-integrity_start),
                      flush=True)
                proofs=target.execute("SELECT COUNT(*) FROM proof_versions").fetchone()[0]
                runs=target.execute("SELECT COUNT(*) FROM scan_runs").fetchone()[0]
        os.replace(partial,destination)
    finally:
        partial.unlink(missing_ok=True)
    return {"ok":True,"path":str(destination),"sqlite_integrity":"ok","scan_runs":runs,
            "proof_versions":proofs,"email_sent":False,
            "off_machine_backup_still_required":True}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    args=p.parse_args()
    print(json.dumps(backup(args.data_root),ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
