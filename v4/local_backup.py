"""Safe online SQLite backup of local V4 shadow ledger; never sends mail."""
from __future__ import annotations
import argparse
import json
import sqlite3
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
    if destination.exists():
        raise FileExistsError("BACKUP_TARGET_EXISTS")
    with closing(sqlite3.connect(f"file:{source.as_posix()}?mode=ro",uri=True)) as original:
        with closing(sqlite3.connect(destination)) as target:
            original.backup(target)
            result=target.execute("PRAGMA integrity_check").fetchone()[0]
            if result!="ok":
                raise RuntimeError("BACKUP_INTEGRITY_FAILED:"+str(result))
            proofs=target.execute("SELECT COUNT(*) FROM proof_versions").fetchone()[0]
            runs=target.execute("SELECT COUNT(*) FROM scan_runs").fetchone()[0]
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
