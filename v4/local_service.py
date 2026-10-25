"""Windowless scheduled shadow job with opt-in research-only mail digests.

Use with Windows Task Scheduler and pythonw.exe. All stdout/stderr goes into the
private local data root; exceptions are caught so pythonw never opens an error box.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from pathlib import Path

from v4.local_backup import backup
from v4.local_run import run
from v4.structure_registry import STRUCTURES

MIN_FREE_GIB = 20
BACKUP_AFTER_HOURS = 24


def storage_check(data_root: Path, *, free_bytes: int | None = None) -> dict:
    """Block before fetching a new snapshot if local free space is too low."""
    if free_bytes is None:
        root = data_root
        while not root.exists() and root != root.parent:
            root = root.parent
        free_bytes = shutil.disk_usage(root).free
    return {"free_gib": round(free_bytes / 1024**3, 2),
            "enough_space": free_bytes >= MIN_FREE_GIB * 1024**3}


def backup_due(root: Path, now: datetime) -> bool:
    backups = root / "backups"
    latest = max(backups.glob("v4-shadow-*.sqlite3"), key=lambda p:p.stat().st_mtime,
                 default=None) if backups.exists() else None
    if latest is None:
        return True
    age = now.timestamp() - latest.stat().st_mtime
    return age >= BACKUP_AFTER_HOURS * 3600


def execute(root: Path, *, scanner=run, backup_fn=backup,
            now_fn=lambda: datetime.now(timezone.utc)) -> dict:
    """Run in foreground for testability; scheduler redirects all output."""
    disk = storage_check(root)
    if not disk["enough_space"]:
        return {"status": "SKIPPED_LOW_DISK", "disk": disk, "mail_enabled": False}
    scan = scanner(root)
    if scan.get("status") == "SKIPPED_UPSTREAM_STALE":
        if scan.get("mail_enabled") is not False:
            raise RuntimeError("STALE_SNAPSHOT_MAIL_MUST_REMAIN_DISABLED")
        return {"status":"SKIPPED_UPSTREAM_STALE",
                "reason":"UPSTREAM_PUBLIC_SNAPSHOT_NOT_FRESH",
                "run_folder_name":Path(scan["run_folder"]).name,
                "upstream_sources":scan.get("upstream_sources") or {},
                "mail_enabled":False,"disk":disk}
    if scan.get("status") != "SHADOW_RECORDED" or scan.get("mail_enabled") is not False:
        raise RuntimeError("SHADOW_SCAN_NOT_RECORDED_OR_MAIL_NOT_DISABLED")
    lanes = scan.get("structure_health") or {}
    complete = (
        scan.get("coverage_gate") == "INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED"
        and all(isinstance(lanes.get(lane), dict)
                and lanes[lane].get("status") == "COMPLETE"
                and isinstance(lanes[lane].get("pages"), int)
                and lanes[lane]["pages"] > 0
                and lanes[lane].get("pages_fetched") == lanes[lane]["pages"]
                for lane in STRUCTURES)
    )
    issue = "DEGRADED_PARTIAL_COVERAGE"
    if all((lanes.get(name) or {}).get("status") == "COMPLETE" for name in STRUCTURES):
        if scan.get("source_input_integrity") == "PARTIAL_QUARANTINED":
            issue = "DEGRADED_INPUT_QUARANTINE"
    result = {"status":"SHADOW_RECORDED" if complete else issue,
              "run_folder_name":Path(scan["run_folder"]).name,
              "coverage_gate":scan.get("coverage_gate"),
              "source_input_integrity":scan.get("source_input_integrity"),
              "invalid_public_orders":scan.get("invalid_public_orders"),
              "invalid_structure_orders":scan.get("invalid_structure_orders"),
              "rejected_input_orders":scan.get("rejected_input_orders"),
              "zero_remaining_public_orders":scan.get("zero_remaining_public_orders"),
              "zero_remaining_structure_orders":scan.get("zero_remaining_structure_orders"),
              "structure_status":{lane:(lanes.get(lane) or {}).get("status", "MISSING")
                                  for lane in STRUCTURES},
              # Only fixed diagnostic codes/counters, never worker HTTP bodies
              # or authentication secrets. Make the failure actionable.
              "failed_structure_diagnostics":{
                  lane:{
                      "reason":info.get("reason", "UNSPECIFIED"),
                      "http_status":info.get("http_status"),
                      "failed_page":info.get("failed_page"),
                      "pages_fetched":info.get("pages_fetched"),
                      "transient_retries":info.get("transient_retries"),
                  }
                  for lane in STRUCTURES
                  for info in [lanes.get(lane) or {}]
                  if info.get("status") != "COMPLETE"
              },
              "sqlite_unique_proofs":scan.get("sqlite_unique_proofs"),
              "backup": "NOT_DUE","mail_enabled": False,"disk":disk}
    if backup_due(root,now_fn()):
        backed = backup_fn(root)
        if backed.get("sqlite_integrity") != "ok":
            raise RuntimeError("BACKUP_INTEGRITY_NOT_OK")
        result["backup"] = "COMPLETE"
        result["backup_proofs"] = backed["proof_versions"]
        # Retention is strictly post-backup and never allowed to affect the
        # already-verified scan or either notification channel.
        if backed.get("path"):
            try:
                from v4.storage_retention import rotate_backups
                result["backup_retention"] = rotate_backups(
                    root, apply=True, expected_newest=Path(backed["path"]))
            except Exception as exc:
                # Preserve the new backup and all old copies on any safety
                # check or filesystem failure. Never print credentials.
                result["backup_retention"] = {
                    "status": "BLOCKED",
                    "error_type": type(exc).__name__,
                }
    return result


def post_scan_hot_retention(root: Path) -> dict:
    """Fail-open maintenance AFTER notification attempts; only activated
    hot-policy databases may lose verified, cold-archived duplicate rows.
    """
    try:
        from v4.hot_retention import maintain
        return maintain(root,apply=True,max_runs=1)
    except Exception as exc:
        return {"status":"BLOCKED", "error_type":type(exc).__name__,
                "scanner_and_mail_unchanged":True}


def main() -> int:
    p=argparse.ArgumentParser(description="Silent Windows V4 scan and opt-in research email digests")
    p.add_argument("--data-root", type=Path, default=Path.home()/"EVE-V4-Data")
    args=p.parse_args()
    root=args.data_root.resolve()
    logs=root/"logs"
    try:
        logs.mkdir(parents=True,exist_ok=True)
        with (logs/"shadow-task.log").open("a",encoding="utf-8") as log:
            with redirect_stdout(log), redirect_stderr(log):
                print("START",datetime.now(timezone.utc).isoformat(),flush=True)
                try:
                    result=execute(root)
                    print("RESULT",json.dumps(result,ensure_ascii=False),flush=True)
                    if result.get("status") == "SKIPPED_UPSTREAM_STALE":
                        # A normal no-data cycle: never re-mail the previous
                        # completed scan or manufacture candidates from a
                        # delayed upstream snapshot.
                        print("RESEARCH_MAIL_SKIPPED UPSTREAM_SNAPSHOT_STALE",
                              flush=True)
                        return 0
                    if result.get("status") != "SHADOW_RECORDED":
                        # Keep a prominent, dedicated coverage alert via the
                        # existing research-only mail paths, but render() must
                        # suppress ALL opportunity candidates on partial input.
                        # The scheduler still returns exit code 2 below.
                        print("REVIEW_MAIL_WARNING INCOMPLETE_SOURCE_COVERAGE",
                              flush=True)
                    # Independent opt-in research mail channels. Failure of
                    # either sender must NOT suppress the other sender. Both
                    # channels are separate from formal production alerts.
                    delivery_failure = False
                    try:
                        from v4.research_mail import send_review
                        mail = send_review(root, expected_run=result.get("run_folder_name"))
                        print("REVIEW_MAIL",json.dumps(mail,ensure_ascii=False),flush=True)
                    except Exception as mail_exc:
                        from v4.mail_diagnostics import ALLOWED_ERROR_CODES
                        reason = str(mail_exc)
                        code = reason if reason in ALLOWED_ERROR_CODES else "UNCLASSIFIED"
                        print("REVIEW_MAIL_FAILED",type(mail_exc).__name__,code,flush=True)
                        delivery_failure = True
                    try:
                        from v4.game_mail_review import send_review_to_game
                        game_mail = send_review_to_game(
                            root, expected_run=result.get("run_folder_name"))
                        print("GAME_REVIEW_MAIL",json.dumps(game_mail,ensure_ascii=False),flush=True)
                        if game_mail.get("recipient_failure_count", 0) > 0 or (
                            game_mail.get("status") == "V4_GAME_RESEARCH_MAIL_RECIPIENT_FAILED"):
                            delivery_failure = True
                    except Exception as game_exc:
                        from v4.mail_diagnostics import ALLOWED_ERROR_CODES
                        reason = str(game_exc)
                        code = (reason if reason in ALLOWED_ERROR_CODES
                                or reason in ("GAME_MAIL_LATEST_RUN_MISMATCH",
                                              "GAME_MAIL_NON_JITA_PRICING_FORBIDDEN",
                                              "GAME_MAIL_SENDER_NOT_VERIFIED",
                                              "GAME_MAIL_RECEIPT_INCONSISTENT")
                                else "UNCLASSIFIED")
                        print("GAME_REVIEW_MAIL_FAILED",type(game_exc).__name__,code,flush=True)
                        delivery_failure = True
                    # Retention runs *after* both research delivery paths.
                    # It cannot block opportunity push or change mail status.
                    # Unmarked legacy hot DB always returns NOT_ENABLED.
                    housekeeping=post_scan_hot_retention(root)
                    print("HOT_PROOF_RETENTION",
                          json.dumps(housekeeping,ensure_ascii=False),
                          flush=True)
                    if delivery_failure:
                        return 3
                    return 0 if result.get("status") == "SHADOW_RECORDED" else 2
                except Exception as exc:
                    print("FAILED",type(exc).__name__,str(exc),flush=True)
                    traceback.print_exc(file=log)
                    return 1
    except Exception:
        # pythonw.exe must never surface a GUI exception. In the very rare case
        # logs cannot be written, the Windows task exit code is nonzero.
        return 1


if __name__=="__main__":
    sys.exit(main())
