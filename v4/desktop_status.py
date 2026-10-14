"""Lightweight, read-only V4 desktop monitor snapshot.

No network, no API keys, no SQL writes and no task controls. Reads only the
small, existing manifest/report files and the tail of the scheduled-job log.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _json_file(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def _log_tail(path: Path, max_bytes: int = 128 * 1024) -> str:
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            n = f.tell()
            f.seek(max(0, n - max_bytes))
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _log_events(log_text: str) -> dict:
    """Only the last START section determines the current scan phase."""
    lines = log_text.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith("START ")]
    recent = lines[starts[-1]:] if starts else []
    results = []
    for line in lines:
        if line.startswith("RESULT "):
            try:
                r = json.loads(line[7:])
                if isinstance(r, dict):
                    results.append(r)
            except ValueError:
                pass
    completed = next((line[7:] for line in reversed(recent)
                      if line.startswith("FAILED ")), None)
    latest_result = results[-1] if results else {}
    phase = "初始化"
    for line in recent:
        if line.startswith("full_scan: starting"):
            phase = "公开市场采集"
        elif line.startswith("full_scan: completed"):
            phase = "公开市场完成"
        elif line.startswith("deep_scan: starting"):
            phase = "建筑与合同分析"
        elif line.startswith("deep_scan: completed"):
            phase = "分析完成，核验入库"
        elif line.startswith("RESULT "):
            phase = "本轮已结束"
        elif line.startswith("FAILED "):
            phase = "执行异常"
    return {"phase": phase, "last_result": latest_result,
            "last_failed": completed, "start_line":
            next((line[6:] for line in recent if line.startswith("START ")), None),
            "last_section_has_result": any(line.startswith("RESULT ") for line in recent),
            "last_section_has_failure": completed is not None}


def _last_completed_run(run_dirs: list[Path]) -> tuple[dict, dict, str | None]:
    for folder in run_dirs:
        manifest = _json_file(folder / "manifest.json")
        if manifest.get("status") == "SHADOW_RECORDED":
            return manifest, _json_file(folder / "deep_shadow.json"), folder.name
    return {}, {}, None


def read_snapshot(data_root: Path, task: dict | None = None) -> dict:
    """Load a cheap UI snapshot; requires no pandas, scheduler or network."""
    root = Path(data_root)
    task = task or {}
    task_state = str(task.get("state") or "Unknown")
    runs_root = root / "runs"
    try:
        runs = sorted((p for p in runs_root.iterdir() if p.is_dir()), reverse=True)
    except OSError:
        runs = []
    current = _json_file(runs[0] / "manifest.json") if runs else {}
    completed, deep, completed_folder = _last_completed_run(runs)
    event = _log_events(_log_tail(root / "logs" / "shadow-task.log"))
    latest_result = event["last_result"]
    # A shell task returning exit code 2 is an acknowledged degraded scan.
    last_code = task.get("last_result")
    try:
        last_code = int(last_code) if last_code is not None else None
    except (TypeError, ValueError):
        last_code = None
    running = task_state.lower() == "running"
    if running:
        status = "RUNNING"
    elif task_state.lower() == "disabled":
        status = "DISABLED"
    elif task_state.lower() == "missing":
        status = "TASK_MISSING"
    elif event["last_section_has_failure"]:
        status = "FAILED"
    elif latest_result:
        status = str(latest_result.get("status") or "UNKNOWN")
    elif current.get("status") == "FAILED":
        status = "FAILED"
    elif completed.get("status") == "SHADOW_RECORDED":
        status = ("SHADOW_RECORDED" if completed.get("coverage_gate") ==
                  "INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED"
                  else "DEGRADED_PARTIAL_COVERAGE")
    else:
        status = "NO_HISTORY"

    if not running and status == "SHADOW_RECORDED" and last_code not in (None, 0):
        status = "CHECK_TASK_RESULT"
    if not running and last_code == 1:
        status = "FAILED"
    if running:
        phase = event["phase"]
    else:
        phase = "待命" if task_state.lower() == "ready" else "未运行"
    health = (completed.get("structure_health") or
              deep.get("structure_health") or {})
    sources = {name: str((health.get(name) or {}).get("status") or "UNKNOWN")
               for name in ("four_h", "cj", "o4t")}
    result_folder = latest_result.get("run_folder_name")
    if not running and event["last_section_has_failure"]:
        # Never show the previous success as the latest outcome after failure.
        last_result_status = "FAILED"
    elif result_folder and result_folder != completed_folder:
        last_result_status = latest_result.get("status")
    else:
        last_result_status = latest_result.get("status") or (
            "SHADOW_RECORDED" if completed and
            completed.get("coverage_gate") ==
            "INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED"
            else "PARTIAL_UNVERIFIED" if completed else "NO_HISTORY")
    return {
        "status": status,
        "task_state": task_state,
        "phase": phase,
        "next_run": task.get("next_run"),
        "last_run": task.get("last_run"),
        "last_result_code": last_code,
        "run_folder": (runs[0].name if runs else None),
        "last_completed_folder": completed_folder,
        "latest_result_status": last_result_status,
        "structures": sources,
        "model_candidates": deep.get("model_candidates"),
        "market_examined": deep.get("market_proofs_examined"),
        "contract_examined": deep.get("contract_approved_locations_examined"),
        "research_gmail_enabled": _json_file(root / "config" / "research_gmail.json").get("enabled") is True,
        "research_game_enabled": _json_file(root / "config" / "eve_game_mail_review.json").get("enabled") is True,
        "proofs": completed.get("sqlite_unique_proofs"),
        "invalid_public_orders": completed.get("invalid_public_orders"),
        "zero_remaining_public_orders": completed.get("zero_remaining_public_orders"),
        "coverage_gate": completed.get("coverage_gate"),
        "source_input_integrity": completed.get("source_input_integrity"),
        "elapsed_start": current.get("started_at") if running else None,
        "mail_enabled": False,
        "read_only": True,
        "poll_source": "LOCAL_FILES_AND_WINDOWS_TASK_SCHEDULER",
        "last_log_error": (event["last_failed"][:120]
                           if event["last_failed"] else None),
    }


def human_clock(iso_value) -> str:
    if not iso_value:
        return "--:--"
    try:
        stamp = datetime.fromisoformat(str(iso_value).replace("Z", "+00:00"))
        if stamp.tzinfo is not None:
            stamp = stamp.astimezone()
        return stamp.strftime("%m/%d %H:%M")
    except (ValueError, TypeError, OverflowError):
        return "--:--"


def elapsed_clock(iso_value) -> str:
    if not iso_value:
        return "--:--"
    try:
        start = datetime.fromisoformat(str(iso_value).replace("Z", "+00:00"))
        if start.tzinfo is None:
            return "--:--"
        seconds = max(0, int((datetime.now(timezone.utc) - start).total_seconds()))
        return "%02d:%02d" % (seconds // 60, seconds % 60)
    except (ValueError, TypeError, OverflowError):
        return "--:--"
