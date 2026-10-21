"""Read-only four-station V4 desktop monitoring adapter.

Uses only local files written by existing scheduled tasks. Never touches
the Worker, API keys, EVE SSO, order data, or mail transmission.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from v4.structure_registry import BASE_LANES, BANESTAR_LANE, ENABLE_CONTENT

BASE_NAMES = tuple(row[0] for row in BASE_LANES)
BANESTAR = BANESTAR_LANE[0]
LABELS = {row[0]: row[1] for row in BASE_LANES + (BANESTAR_LANE,)}


def _json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, UnicodeError, ValueError):
        return {}


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _activation_time(root: Path) -> float | None:
    path = root / "config" / "banestar-market.enabled"
    try:
        if path.read_text(encoding="utf-8").strip() == ENABLE_CONTENT:
            return path.stat().st_mtime
    except (OSError, UnicodeError):
        pass
    return None


def _mail_status(value, channel: str) -> str:
    if not isinstance(value, dict):
        return "UNKNOWN"
    status = value.get("status")
    if not isinstance(status, str):
        return "UNKNOWN"
    allowed = (
        {"GAME_MAIL_SENT", "GAME_MAIL_ALREADY_SENT",
         "NO_NEW_QUALIFIED_LEADS", "OPPORTUNITY_CHANNEL_FAILED"}
        if channel == "game"
        else {"GMAIL_SENT", "GMAIL_ALREADY_SENT",
              "NO_NEW_QUALIFIED_LEADS", "OPPORTUNITY_CHANNEL_FAILED"}
    )
    return status if status in allowed else "UNKNOWN"


def read_opportunity(root: Path, lanes: tuple[str, ...],
                     activated_at: float | None) -> dict:
    """Most recent whole-cycle opportunity proof, never raw market rows."""
    result = {
        "status": "WAITING_FIRST_CYCLE", "reported_at": None,
        "qualified_model_leads": None, "station": None,
        "game_mail": "UNKNOWN", "gmail": "UNKNOWN",
    }
    folder = root / "opportunity-push"
    try:
        files = sorted(
            (p for p in folder.glob("*.json") if p.name != "state.json"),
            key=_mtime, reverse=True,
        )
    except OSError:
        return result
    for file in files[:10]:
        if activated_at is not None and _mtime(file) <= activated_at:
            break
        report = _json(file)
        if report.get("status") != "OPPORTUNITY_NOTIFICATION_CYCLE_COMPLETE":
            # A newer malformed/incomplete summary must not be skipped just
            # to reuse an earlier green success.
            return {**result, "status": "INVALID_REPORT"}
        health = report.get("authenticated_structure_health")
        if not isinstance(health, dict) or not all(
            isinstance(health.get(lane), dict)
            and health[lane].get("status") == "COMPLETE"
            and type(health[lane].get("pages")) is int
            and health[lane]["pages"] >= 1
            for lane in lanes
        ):
            return {**result, "status": "INCOMPLETE_COVERAGE"}
        channels = report.get("notification_channels")
        if not isinstance(channels, dict):
            channels = {}
        by_station = report.get("by_station")
        if not isinstance(by_station, dict):
            by_station = {}
        station = by_station.get("74L2-U", {}) if activated_at is not None else None
        if station is not None and not isinstance(station, dict):
            station = None
        count = report.get("qualified_model_leads")
        if type(count) is not int or count < 0:
            count = None
        # The hourly opportunity job can stop without writing another report.
        # A past success is not current health after three hours of silence.
        age_seconds = time.time() - _mtime(file)
        return {
            "status": ("STALE_REPORT" if age_seconds > 3 * 3600
                       else "COMPLETE"),
            "reported_at": report.get("finished_at"),
            "qualified_model_leads": count,
            "station": station,
            "game_mail": _mail_status(channels.get("game"), "game"),
            "gmail": _mail_status(channels.get("gmail"), "gmail"),
        }
    return result


def read_station_scope(root: Path, *, current: dict, completed: dict,
                       completed_folder: str | None,
                       latest_result: dict, runs: list[Path]) -> dict:
    """Never let a historical green 3-station run validate a new fourth lane."""
    activated_at = _activation_time(root)
    enabled = activated_at is not None
    lanes = BASE_NAMES + ((BANESTAR,) if enabled else ())
    current_path = runs[0] / "manifest.json" if runs else None
    current_finished = current.get("status") == "SHADOW_RECORDED"
    current_fresh = bool(
        enabled and current_path and current_finished
        and _mtime(current_path) > activated_at
    )
    prior_path = (root / "runs" / completed_folder / "manifest.json"
                  if completed_folder else None)
    prior_fresh = bool(
        enabled and prior_path and _mtime(prior_path) > activated_at
    )
    new_failure = bool(
        enabled and current_path and _mtime(current_path) > activated_at
        and current.get("status") == "FAILED"
    )
    if new_failure:
        # Do not let an earlier successful four-station run conceal a newer
        # failed attempt. The failure itself has no verified lane statuses.
        states = {lane: "MISSING" for lane in lanes}
        scan_status = "INCOMPLETE_COVERAGE"
    elif enabled and not current_fresh and not prior_fresh:
        states = {lane: "PENDING_FIRST_RUN" for lane in lanes}
        scan_status = "WAITING_NEW_SCOPE"
    else:
        # Prefer the newest *finished* run; STARTED/STALE never supersede a
        # prior fully recorded four-station scan.
        health = (current.get("structure_health") if current_finished
                  else completed.get("structure_health")) or {}
        # If local_service has a status for this same run, it is useful when
        # the manifest is partial, but never mix results from different runs.
        matching_log = (
            latest_result.get("run_folder_name") == (runs[0].name if runs else None)
            and current_finished
        )
        if matching_log:
            log_health = latest_result.get("structure_status")
            if isinstance(log_health, dict):
                health = {lane: {"status": log_health.get(lane, "MISSING")}
                          for lane in lanes}
        missing_label = "MISSING" if enabled else "UNKNOWN"
        states = {
            lane: (str((health.get(lane) or {}).get("status") or missing_label))
            for lane in lanes
        }
        scan_status = (
            "COMPLETE" if all(v == "COMPLETE" for v in states.values())
            else "INCOMPLETE_COVERAGE"
        )
    return {
        "banestar_enabled": enabled,
        "labels": {lane: LABELS[lane] for lane in lanes},
        "structures": states,
        "scan_scope_status": scan_status,
        "opportunity": read_opportunity(root, lanes, activated_at),
    }
