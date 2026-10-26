"""V4 bounded whole-disk capacity telemetry; never deletes business evidence.

Default report() only reads file metadata. record() stores up to 30 days of
hourly observations in a small atomic JSON history for growth estimates.
No filesystem cleanup, snapshot deletion, database changes or network.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

GIB = 1024 ** 3
MIN_FREE_GIB = 20
WARNING_FREE_GIB = 40
HISTORY_LIMIT = 720
HISTORY_FILE = Path("logs") / "storage-capacity-history.json"
SENSITIVE_TOP = ("sqlite", "runs", "backups", "cold-proof-archives",
                 "hot-stage", "hot-cutover-rollback",
                 "esi-parallel-validation", "logs")
MAX_FILES = 500000


def _files(root: Path) -> dict:
    counts = {}
    seen = 0
    errors = []
    if not root.exists():
        return {"total_bytes": 0, "files": 0, "categories": {},
                "status": "ROOT_MISSING"}
    if root.is_symlink() or not root.is_dir():
        return {"total_bytes": 0, "files": 0, "categories": {},
                "status": "ROOT_UNSAFE"}
    total = 0
    for base, dirs, files in os.walk(root, topdown=True, followlinks=False):
        here = Path(base)
        # Skip symlinked subdirectories; a link can point outside the data root.
        dirs[:] = [d for d in dirs if not (here / d).is_symlink()]
        for filename in files:
            candidate = here / filename
            if candidate.is_symlink():
                continue
            try:
                size = candidate.stat().st_size
                category = candidate.relative_to(root).parts[0]
            except (ValueError, OSError, IndexError):
                errors.append("FILE_STAT_FAILED")
                continue
            counts[category] = counts.get(category, 0) + size
            total += size
            seen += 1
            if seen > MAX_FILES:
                return {"total_bytes": total, "files": seen,
                        "categories": counts, "status": "FILE_LIMIT_EXCEEDED"}
    return {"total_bytes": total, "files": seen,
            "categories": counts, "status": "PARTIAL" if errors else "COMPLETE"}


def _history(root: Path) -> list:
    path = root / HISTORY_FILE
    if not path.is_file() or path.is_symlink():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        values = raw.get("samples", []) if isinstance(raw, dict) else []
        if not isinstance(values, list):
            return []
        return [v for v in values[-HISTORY_LIMIT:]
                if isinstance(v, dict) and
                isinstance(v.get("time"), str) and
                isinstance(v.get("free_bytes"), int)]
    except (ValueError, UnicodeError, OSError):
        return []


def _growth(samples: list, free_now: int, now: datetime) -> dict:
    # At least six hours of history; 1-hour noise is not a useful forecast.
    baseline = None
    for sample in samples:
        try:
            stamp = datetime.fromisoformat(sample["time"])
            hours = (now - stamp).total_seconds() / 3600
            if 6 <= hours <= 30:
                baseline = (sample, hours)
                break
        except (TypeError, ValueError):
            continue
    if baseline is None:
        return {"status": "INSUFFICIENT_HISTORY", "daily_free_gib_change": None,
                "days_until_20_gib": None}
    old, hours = baseline
    daily_delta = (free_now - old["free_bytes"]) / GIB * 24 / hours
    until = None
    if daily_delta < -0.01 and free_now > MIN_FREE_GIB * GIB:
        until = (free_now / GIB - MIN_FREE_GIB) / -daily_delta
    return {"status": "OBSERVED_NOT_FORECAST_GUARANTEE",
            "daily_free_gib_change": round(daily_delta, 3),
            "days_until_20_gib": round(until, 2) if until is not None else None}


def report(root: Path, *, free_bytes: int | None = None,
           now: datetime | None = None) -> dict:
    root = Path(root).resolve()
    now = now or datetime.now(timezone.utc)
    usage = shutil.disk_usage(root if root.is_dir() else root.parent)
    free = usage.free if free_bytes is None else free_bytes
    survey = _files(root)
    samples = _history(root)
    trend = _growth(samples, free, now)
    severity = ("STOP" if free < MIN_FREE_GIB * GIB else
                "WARNING" if free < WARNING_FREE_GIB * GIB or
                (trend["days_until_20_gib"] is not None and
                 trend["days_until_20_gib"] <= 7) else "OK")
    # An incomplete directory survey can hide a large unobserved footprint.
    if survey["status"] != "COMPLETE" and severity == "OK":
        severity = "UNKNOWN"
    sections = {
        name: {"gib": round(survey["categories"].get(name, 0) / GIB, 3)}
        for name in SENSITIVE_TOP
    }
    other = sum(v for k, v in survey["categories"].items()
                if k not in SENSITIVE_TOP)
    sections["other"] = {"gib": round(other / GIB, 3)}
    return {
        "status": "READ_ONLY_STORAGE_GOVERNOR",
        "severity": severity,
        "free_gib": round(free / GIB, 2),
        "total_gib": round(usage.total / GIB, 2),
        "project_gib": round(survey["total_bytes"] / GIB, 3),
        "project_file_count": survey["files"],
        "inventory_status": survey["status"],
        "sections": sections,
        "growth": trend,
        "history_samples": len(samples),
        "automatic_raw_snapshot_deletion_enabled": False,
        "automatic_database_cutover_enabled": False,
        "files_deleted": 0,
        "database_modified": False,
    }


def record(root: Path, *, free_bytes: int | None = None,
           now: datetime | None = None) -> dict:
    """Capture an observation; never modify anything except this bounded log."""
    root = Path(root).resolve()
    now = now or datetime.now(timezone.utc)
    result = report(root, free_bytes=free_bytes, now=now)
    if not root.is_dir() or result["inventory_status"] != "COMPLETE":
        return {**result, "history_recorded": False}
    samples = _history(root)
    if samples:
        try:
            recent = datetime.fromisoformat(samples[-1]["time"])
            if 0 <= (now - recent).total_seconds() < 3000:
                return {**result, "history_recorded": False}
        except ValueError:
            pass
    free = (shutil.disk_usage(root).free if free_bytes is None else free_bytes)
    samples.append({"time": now.isoformat(), "free_bytes": int(free),
                    "project_gib": result["project_gib"],
                    "sections": result["sections"]})
    samples = samples[-HISTORY_LIMIT:]
    path = root / HISTORY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():
        return {**result, "history_recorded": False,
                "history_error": "UNSAFE_HISTORY_PATH"}
    temporary = path.with_suffix(".json.part")
    if temporary.exists() or temporary.is_symlink():
        return {**result, "history_recorded": False,
                "history_error": "HISTORY_PARTIAL_EXISTS"}
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump({"schema": 1, "samples": samples}, handle,
                      ensure_ascii=False, separators=(",", ":"))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return {**result, "history_recorded": True}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="V4 whole-disk capacity health; no evidence cleanup")
    parser.add_argument("--data-root", type=Path,
                        default=Path.home() / "EVE-V4-Data")
    parser.add_argument("--record", action="store_true",
                        help="Persist one bounded usage observation (no deletion)")
    args = parser.parse_args()
    result = (record(args.data_root) if args.record else
              report(args.data_root))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
