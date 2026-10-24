"""Read-only V4 directory and SQLite page usage inventory.

No scans, mail, network, cleanup, PRAGMA VACUUM or table mutation.
Use --deep only when it is acceptable to read SQLite's page statistics.
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path

GIB = 1024**3


def _directory_totals(root: Path) -> dict:
    stats = defaultdict(lambda: [0, 0])
    for item in root.rglob("*"):
        if item.is_symlink() or not item.is_file():
            continue
        try:
            parent = item.relative_to(root).parts[0]
            size = item.stat().st_size
        except (ValueError, OSError, IndexError):
            continue
        stats[parent][0] += size
        stats[parent][1] += 1
    return {
        name: {"gib": round(nbytes/GIB, 3), "files": files}
        for name, (nbytes, files) in sorted(
            stats.items(), key=lambda item: -item[1][0])
    }


def _backup_inventory(root: Path) -> dict:
    """List backup directory files, including unexpected .part/journal files."""
    folder=root/"backups"
    if not folder.is_dir() or folder.is_symlink():
        return {"status": "NOT_FOUND_OR_UNSAFE"}
    entries=[]
    for p in folder.iterdir():
        if p.is_symlink() or not p.is_file():
            continue
        try:
            stat=p.stat()
        except OSError:
            continue
        entries.append({"name":p.name,
                        "gib":round(stat.st_size/GIB,3),
                        "bytes":stat.st_size})
    entries.sort(key=lambda x:x["bytes"],reverse=True)
    return {"status":"READ_ONLY", "files":len(entries),
            "largest_files":entries[:15],
            "unrecognized_files":[
                x["name"] for x in entries
                if not (x["name"].startswith("v4-shadow-")
                        and x["name"].endswith(".sqlite3"))]}


def _proof_sample(conn: sqlite3.Connection, *, count: int,
                  samples: int=128) -> dict:
    """Estimate JSON payload space without requiring the dbstat extension.

    Bounded indexed lookups by rowid; no full-text read of all proof rows.
    """
    if count <= 0:
        return {"status":"NO_PROOFS"}
    upper=conn.execute("SELECT MAX(rowid) FROM proof_versions").fetchone()[0]
    if not isinstance(upper,int) or upper<1:
        return {"status":"UNAVAILABLE"}
    rng=random.Random(428709)
    lengths=[]
    for _ in range(samples):
        row=conn.execute(
            "SELECT LENGTH(CAST(proof_json AS BLOB)) FROM proof_versions "
            "WHERE rowid>=? ORDER BY rowid LIMIT 1",
            (rng.randint(1,upper),)).fetchone()
        if row and isinstance(row[0],int):
            lengths.append(row[0])
    if not lengths:
        return {"status":"NO_SAMPLES"}
    average=sum(lengths)/len(lengths)
    return {
        "status":"ESTIMATE_NOT_EXACT",
        "sample_rows":len(lengths),
        "avg_proof_json_bytes":round(average),
        "estimated_proof_json_gib":round(average*count/GIB,3),
        "explanation":"Sampled proof_json only; excludes primary keys, SQLite page overhead and indexes",
    }


def _sqlite_snapshot(path: Path, *, deep=False) -> dict:
    if not path.is_file():
        return {"status": "NOT_FOUND"}
    result = {"status": "READ_ONLY",
              "file_gib": round(path.stat().st_size/GIB, 3)}
    with closing(sqlite3.connect(
            "file:"+path.resolve().as_posix()+"?mode=ro", uri=True,
            timeout=30)) as conn:
        page_size=conn.execute("PRAGMA page_size").fetchone()[0]
        total=conn.execute("PRAGMA page_count").fetchone()[0]
        free=conn.execute("PRAGMA freelist_count").fetchone()[0]
        result.update({
            "page_size_bytes": page_size,
            "allocated_gib": round(total*page_size/GIB, 3),
            "free_pages_gib": round(free*page_size/GIB, 3),
            # SQLite VACUUM can also compact partially empty *allocated*
            # pages. freelist_count is NOT an upper bound on VACUUM savings.
            "vacuum_savings_estimate": "UNKNOWN_WITHOUT_PAGE_UTILIZATION",
        })
        if deep:
            # dbstat is read-only; groups actual SQLite B-tree page space,
            # not just raw JSON length. Available on standard Python SQLite.
            try:
                rows=conn.execute(
                    "SELECT name, SUM(pgsize) AS bytes FROM dbstat "
                    "GROUP BY name ORDER BY bytes DESC").fetchall()
                result["btree_gib"]={
                    str(name): round(int(size)/GIB, 3)
                    for name, size in rows
                }
            except sqlite3.DatabaseError:
                result["btree_gib"]={"status":"DBSTAT_UNAVAILABLE"}
            try:
                result["scan_run_count"] = conn.execute(
                    "SELECT COUNT(*) FROM scan_runs").fetchone()[0]
                result["proof_row_count"] = conn.execute(
                    "SELECT COUNT(*) FROM proof_versions").fetchone()[0]
                result["proof_json_sample"] = _proof_sample(
                    conn,count=result["proof_row_count"])
                result["sql_indexes"] = [
                    row[0] for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='index' "
                        "ORDER BY name")]
                result["recent_scan_runs"] = [
                    {"run_id":r[0],"proof_count":r[1],"audited_at":r[2]}
                    for r in conn.execute(
                        "SELECT run_id,proof_count,audited_at FROM scan_runs "
                        "ORDER BY audited_at DESC LIMIT 3")]
            except sqlite3.DatabaseError:
                result["row_counts_status"] = "UNAVAILABLE"
    return result


def inspect(root: Path, *, deep=False) -> dict:
    root=Path(root).resolve()
    return {
        "status": "READ_ONLY_STORAGE_AUDIT",
        "data_root": str(root),
        "directories": _directory_totals(root),
        "backup_inventory": _backup_inventory(root),
        "hot_sqlite": _sqlite_snapshot(
            root/"sqlite"/"v4-shadow.sqlite3",deep=deep),
        "historical_rows_deleted": False,
        "backup_files_deleted": False,
        "off_machine_backup_still_required": True,
    }


def main() -> None:
    p=argparse.ArgumentParser(description="V4 storage use (read only)")
    p.add_argument("--data-root",type=Path,
                   default=Path.home()/"EVE-V4-Data")
    p.add_argument("--deep",action="store_true",
                   help="Count historical proof rows and inspect each B-tree")
    args=p.parse_args()
    print(json.dumps(inspect(args.data_root,deep=args.deep),
                     ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
