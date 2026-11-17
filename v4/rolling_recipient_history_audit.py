"""Read-only historical EVE V4 research-mail receipt migration audit.

This does not modify/repair receipts, approve a migration, change rolling72
eligibility, send mail, alter a backup, or delete *any* evidence. The observed
past dual receipts do not by themselves prove the effective recipient policy.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from v4.game_mail_review import (EXPECTED_SENDER_ID, HUNTER_CHARACTER_ID,
                                 ALLOWED_RECIPIENTS)
from v4.rolling_cleanup import KEEP, _history
from v4.rolling_retention import _json

OFFICIAL_SOURCE = "EVE_OFFICIAL_MAIL_VIA_EXISTING_WORKER"
MIKE_ID = ALLOWED_RECIPIENTS["MikeChong"]


def _run_start(folder: str) -> datetime | None:
    try:
        return datetime.strptime(folder[:16], "%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _confirmed_time(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        point = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return point.astimezone(timezone.utc) if point.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def _game_receipts(root: Path, folder: str) -> tuple[list[dict], int]:
    directory = root / "mail-review" / "eve-receipts"
    paths = [directory / (folder + ".json")]
    if directory.is_dir() and not directory.is_symlink():
        paths.extend(sorted(directory.glob(folder + "-*.json")))
    good, rejected = [], 0
    started = _run_start(folder)
    for path in paths:
        if not path.is_file() or path.is_symlink():
            continue
        row = _json(path)
        point = _confirmed_time(row.get("confirmed_at")) if row else None
        if (not row or row.get("run") != folder or point is None
                or started is None or point < started
                or row.get("source") != OFFICIAL_SOURCE
                or row.get("sender_id") != EXPECTED_SENDER_ID
                or not isinstance(row.get("recipient_id"), int)
                or isinstance(row.get("recipient_id"), bool)
                or row["recipient_id"] <= 0
                or not ((isinstance(row.get("mail_id"), int)
                         and not isinstance(row.get("mail_id"), bool)
                         and row["mail_id"] > 0)
                        or row.get("already_accepted") is True)):
            rejected += 1
            continue
        name, ident = row.get("recipient"), row["recipient_id"]
        if (name in (None, "", "MikeChong") and ident == MIKE_ID):
            name = "MikeChong"
        elif name == "Arb Hunter" and ident == HUNTER_CHARACTER_ID:
            pass
        elif name == "LadyBaBa":
            pass  # Unique historical Lady ID still needs external verification.
        else:
            rejected += 1
            continue
        good.append({"recipient": name, "recipient_id": ident,
                     "confirmed_at": point.isoformat()})
    return good, rejected


def _gmail_confirmed(root: Path, folder: str) -> bool:
    receipt = _json(root / "mail-review" / "receipts" / (folder + ".json"))
    return bool(receipt and receipt.get("run") == folder
                and receipt.get("sent_at"))


def audit_folders(root: Path, folders: list[str]) -> dict:
    """Report worker-confirmed receipt coverage, never deletion eligibility."""
    categories = Counter()
    lady_ids = Counter()
    suspicious = 0
    examples = []
    for folder in folders:
        matches, rejected = _game_receipts(root, folder)
        suspicious += rejected
        names = {r["recipient"] for r in matches}
        lady_ids.update(r["recipient_id"] for r in matches
                        if r["recipient"] == "LadyBaBa")
        if {"MikeChong", "LadyBaBa"}.issubset(names):
            label = "BOTH_LEGACY_WORKER_RECEIPTS"
        elif "MikeChong" in names:
            label = "MIKE_ONLY"
        elif "LadyBaBa" in names:
            label = "LADY_ONLY"
        else:
            label = "NEITHER"
        categories[label] += 1
        if not _gmail_confirmed(root, folder):
            categories["NO_GMAIL_RECEIPT"] += 1
        if label != "BOTH_LEGACY_WORKER_RECEIPTS":
            examples.append({"run_folder": folder, "evidence": label})
    return {
        "status": "READ_ONLY_HISTORICAL_MAIL_AUDIT",
        "source": "WORKER_RECEIPTS_NOT_MIGRATION_APPROVAL",
        "old_runs": len(folders),
        "worker_receipt_coverage": dict(categories),
        "lady_recipient_ids_observed": {str(k): v for k, v in lady_ids.items()},
        "invalid_or_unverifiable_receipts": suspicious,
        "nondual_examples": examples[:20],
        "proves_historical_recipient_policy": False,
        "permitted_to_delete": False,
        "modified": False,
    }


def audit(root: Path) -> dict:
    root = root.resolve()
    source = root / "sqlite" / "v4-shadow.sqlite3"
    if not source.is_file() or source.is_symlink():
        raise RuntimeError("LIVE_SQLITE_UNAVAILABLE")
    with closing(sqlite3.connect(
            "file:" + source.as_posix() + "?mode=ro",
            uri=True, timeout=30)) as db:
        db.execute("PRAGMA query_only=ON")
        run_rows, warnings = _history(root, db)
    if warnings:
        raise RuntimeError("HISTORY_NOT_CONSISTENT")
    report = audit_folders(root, [r[1] for r in run_rows[KEEP:]])
    report["kept_successful_run_window"] = min(KEEP, len(run_rows))
    policy = _json(root / "config" / "rolling72-enabled.json") or {}
    reference = policy.get("backup")
    if isinstance(reference, str):
        bp = Path(reference)
        report["policy_backup_name"] = bp.name
        report["policy_backup_exists"] = bp.is_file()
    else:
        report["policy_backup_name"] = "UNKNOWN"
        report["policy_backup_exists"] = False
    # Never print live config, credentials, tokens, addresses, raw message
    # bodies, recipient-migration timestamps, or protected audit row content.
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-root", type=Path,
                   default=Path.home() / "EVE-V4-Data")
    args = p.parse_args()
    print(json.dumps(audit(args.data_root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
