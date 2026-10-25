"""V4 proof cold archive: lossless, resumable, fail-closed, never mutates live DB.

V4 full scan writes runs/<stamp>/all_proofs.jsonl; local_store persists
the exact raw SHA256 as scan_runs.proof_sha256. Archive only when BOTH agree.
Default is read-only coverage. --apply archives at most 3 old runs by default.
This tool NEVER prunes SQLite, raw runs, backups or live notifications.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

KEEP_RUNS = 72
MIN_FREE_GIB = 30
CHUNK = 1024 * 1024


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ledger_runs(root: Path) -> list[dict]:
    path = root / "sqlite" / "v4-shadow.sqlite3"
    if not path.is_file():
        raise FileNotFoundError("NO_V4_LEDGER")
    uri = "file:" + path.resolve().as_posix() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=30)) as db:
        rows = db.execute(
            "SELECT run_id,status,proof_count,proof_sha256,audited_at "
            "FROM scan_runs ORDER BY audited_at DESC,run_id DESC").fetchall()
    if not rows:
        raise RuntimeError("NO_AUDITED_RUNS")
    result = [dict(zip(("run_id","status","proof_count",
                        "proof_sha256","audited_at"), row)) for row in rows]
    if len({r["run_id"] for r in result}) != len(result):
        raise RuntimeError("DUPLICATE_LEDGER_RUN_ID")
    return result


def source_index(root: Path) -> dict[str, Path]:
    """Only inspect small per-run report JSON files, never source market blobs."""
    folder = root / "runs"
    if not folder.is_dir():
        return {}
    mapping: dict[str, Path] = {}
    duplicate = set()
    for run_folder in folder.iterdir():
        if not run_folder.is_dir() or run_folder.is_symlink():
            continue
        report = run_folder / "deep_shadow.json"
        raw = run_folder / "all_proofs.jsonl"
        if not report.is_file() or report.is_symlink() or raw.is_symlink():
            continue
        try:
            run_id = json.loads(report.read_text(encoding="utf-8")).get("run_id")
        except (OSError, UnicodeError, ValueError):
            continue
        if not isinstance(run_id, str):
            continue
        if run_id in mapping:
            duplicate.add(run_id)
        elif raw.is_file():
            mapping[run_id] = raw
    for run_id in duplicate:
        mapping.pop(run_id, None)
    return mapping


def _archive_paths(root: Path, run_id: str) -> tuple[Path, Path]:
    # Run ID must not control arbitrary output paths.
    import re
    if not re.fullmatch(r"[A-Za-z0-9_-]{5,128}", run_id):
        raise ValueError("UNSAFE_RUN_ID")
    folder = root / "cold-proof-archives"
    return folder / (run_id + ".jsonl.gz"), folder / (run_id + ".manifest.json")


def verify_archive(root: Path, record: dict) -> dict:
    archive, manifest_file = _archive_paths(root, record["run_id"])
    if archive.parent.is_symlink() or archive.is_symlink() or manifest_file.is_symlink():
        raise RuntimeError("COLD_ARCHIVE_UNSAFE_SYMLINK")
    if not manifest_file.is_file() or not archive.is_file():
        raise RuntimeError("COLD_ARCHIVE_INCOMPLETE")
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    if any(data.get(key) != record[key] for key in
           ("run_id", "proof_count", "proof_sha256")):
        raise RuntimeError("COLD_MANIFEST_LEDGER_MISMATCH")
    if data.get("archive_sha256") != _sha_file(archive):
        raise RuntimeError("COLD_ARCHIVE_CHECKSUM_MISMATCH")
    sha = hashlib.sha256()
    rows = 0
    raw_bytes = 0
    with gzip.open(archive, "rb") as source:
        for line in source:
            sha.update(line)
            raw_bytes += len(line)
            if line.strip():
                rows += 1
    if sha.hexdigest() != record["proof_sha256"] or rows != record["proof_count"]:
        raise RuntimeError("COLD_ARCHIVE_CONTENT_MISMATCH")
    if raw_bytes != data.get("raw_bytes"):
        raise RuntimeError("COLD_ARCHIVE_LENGTH_MISMATCH")
    return {"status": "VERIFIED", "run_id": record["run_id"],
            "proof_count": rows, "compressed_bytes": archive.stat().st_size}


def archive_one(root: Path, record: dict, source: Path) -> dict:
    if record["status"] != "SHADOW_VERIFIED_OFFLINE":
        raise RuntimeError("LEDGER_RUN_NOT_VERIFIED")
    archive, manifest_file = _archive_paths(root, record["run_id"])
    if archive.exists() or manifest_file.exists():
        return verify_archive(root, record)
    if not source.is_file() or source.is_symlink():
        raise RuntimeError("RAW_PROOF_SOURCE_MISSING")
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.parent.is_symlink():
        raise RuntimeError("COLD_ARCHIVE_FOLDER_UNSAFE")
    if shutil.disk_usage(root).free < MIN_FREE_GIB * (1024 ** 3):
        raise RuntimeError("INSUFFICIENT_DISK_FOR_COLD_ARCHIVE")
    before = source.stat()
    sha = hashlib.sha256()
    rows = 0
    raw_bytes = 0
    part = None
    try:
        # Temp file lives on same volume so promotion is atomic.
        with tempfile.NamedTemporaryFile(
                dir=archive.parent, prefix=".proof-", suffix=".part",
                delete=False) as temp:
            part = Path(temp.name)
            with source.open("rb") as stream:
                with gzip.GzipFile(fileobj=temp, mode="wb", compresslevel=4,
                                   mtime=0) as compressed:
                    for line in stream:
                        sha.update(line)
                        raw_bytes += len(line)
                        if line.strip():
                            rows += 1
                        compressed.write(line)
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError("RAW_PROOF_CHANGED_DURING_ARCHIVE")
        if sha.hexdigest() != record["proof_sha256"] or rows != record["proof_count"]:
            raise RuntimeError("RAW_PROOF_LEDGER_HASH_OR_COUNT_MISMATCH")
        # Reopen and decompress the candidate, checking bytes before publish.
        check = hashlib.sha256()
        check_rows = 0
        with gzip.open(part, "rb") as stream:
            for line in stream:
                check.update(line)
                if line.strip():
                    check_rows += 1
        if check.hexdigest() != sha.hexdigest() or check_rows != rows:
            raise RuntimeError("COLD_ARCHIVE_ROUNDTRIP_FAILED")
        manifest = {
            "format": "V4_COLD_PROOF_RAW_JSONL_GZIP_V1",
            "run_id": record["run_id"],
            "proof_count": record["proof_count"],
            "proof_sha256": record["proof_sha256"],
            "audited_at": record["audited_at"],
            "source_filename": "all_proofs.jsonl",
            "raw_bytes": raw_bytes,
            "compressed_bytes": part.stat().st_size,
            "archive_sha256": _sha_file(part),
            "original_data_preserved": True,
        }
        if archive.exists() or manifest_file.exists():
            raise RuntimeError("COLD_ARCHIVE_CONCURRENT_PUBLISH")
        # A manifest is the publication marker; never publish it first.
        os.replace(part, archive)
        part = None
        temp_manifest = manifest_file.with_name(manifest_file.name + ".part")
        if temp_manifest.exists():
            raise RuntimeError("COLD_MANIFEST_PARTIAL_EXISTS")
        try:
            with temp_manifest.open("x", encoding="utf-8") as stream:
                json.dump(manifest, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_manifest, manifest_file)
        finally:
            temp_manifest.unlink(missing_ok=True)
        return {"status": "ARCHIVED_VERIFIED", "run_id": record["run_id"],
                "proof_count": rows, "compressed_bytes": archive.stat().st_size,
                "raw_bytes": raw_bytes}
    finally:
        if part is not None:
            part.unlink(missing_ok=True)


def run(root: Path, *, apply=False, keep_runs=KEEP_RUNS,
        limit=3, verify_existing=False) -> dict:
    root = root.resolve()
    if keep_runs < 24:
        raise ValueError("KEEP_RUNS_MUST_BE_AT_LEAST_24")
    records = ledger_runs(root)
    sources = source_index(root)
    older = records[keep_runs:]
    eligible = [r for r in older if r["status"] == "SHADOW_VERIFIED_OFFLINE"]
    missing = [r["run_id"] for r in eligible if r["run_id"] not in sources]
    output = {"status": "READ_ONLY_COVERAGE" if not apply else "ARCHIVE_RUN_COMPLETE",
              "total_ledger_runs": len(records), "hot_run_target": min(len(records), keep_runs),
              "cold_run_candidates": len(eligible),
              "raw_source_available": len(eligible) - len(missing),
              "missing_raw_source_count": len(missing),
              "missing_raw_source_samples": missing[:10],
              "unverified_run_count": len(older) - len(eligible),
              "archived_this_call": 0, "verified_existing": 0,
              "failed": [], "sqlite_modified": False,
              "raw_sources_deleted": False, "no_activation": True}
    if not apply:
        return output
    new_attempts = 0
    # Oldest first; existing verified archives do not consume new-run quota.
    # This makes repeated --apply --limit 3 calls advance through history.
    for record in reversed(eligible):
        archive, manifest = _archive_paths(root, record["run_id"])
        already = archive.exists() or manifest.exists()
        if not already and limit is not None and new_attempts >= limit:
            break
        source = sources.get(record["run_id"])
        if not already and source is None:
            output["failed"].append({"run_id":record["run_id"],
                                     "reason":"RAW_SOURCE_MISSING"})
            continue
        if not already:
            new_attempts += 1
        try:
            result = (verify_archive(root, record) if already else
                      archive_one(root, record, source))
            if result["status"] == "ARCHIVED_VERIFIED":
                output["archived_this_call"] += 1
            else:
                output["verified_existing"] += 1
            print("COLD_RUN", result["status"], record["run_id"],
                  "compressed_bytes", result["compressed_bytes"], flush=True)
        except (OSError, ValueError, RuntimeError, sqlite3.DatabaseError) as exc:
            output["failed"].append({"run_id":record["run_id"],
                                     "reason":str(exc)[:120]})
            print("COLD_RUN_FAILED", record["run_id"], type(exc).__name__, flush=True)
    if output["failed"]:
        output["status"] = "PARTIAL_BLOCKED"
    return output


def main():
    parser = argparse.ArgumentParser(
        description="Archive old immutable V4 proof run artifacts without touching SQLite")
    parser.add_argument("--data-root", type=Path,
                        default=Path.home() / "EVE-V4-Data")
    parser.add_argument("--keep-runs", type=int, default=KEEP_RUNS)
    parser.add_argument("--apply", action="store_true",
                        help="Gzip and independently verify old raw proof runs")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--all", action="store_true",
                        help="Process all older runs (potentially large/long)")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    result = run(args.data_root, apply=args.apply,
                 keep_runs=args.keep_runs,
                 limit=None if args.all else args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
