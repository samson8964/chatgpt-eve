"""Read-only V4 directory and SQLite page usage inventory.

No scans, mail, network, cleanup, PRAGMA VACUUM or table mutation.
Use --deep only when it is acceptable to read SQLite's page statistics.
"""
from __future__ import annotations

import argparse
import json
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
            "possible_vacuum_savings_gib_at_most": round(
                free*page_size/GIB, 3),
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
            except sqlite3.DatabaseError:
                result["row_counts_status"] = "UNAVAILABLE"
    return result


def inspect(root: Path, *, deep=False) -> dict:
    root=Path(root).resolve()
    return {
        "status": "READ_ONLY_STORAGE_AUDIT",
        "data_root": str(root),
        "directories": _directory_totals(root),
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
