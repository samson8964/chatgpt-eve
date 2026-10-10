"""Re-entrant, first-seen Gmail state for market arbitrage (not contracts).

An eligible type can be alerted again after leaving and re-entering the formal
MAIL set, or after a material quote change. Cooldown and pending state prevent
repeat floods and preserve retryability after SMTP failure.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

COLUMNS = ("id", "active", "pending", "last_profit", "last_roi", "last_sent_at", "last_seen_at")


def _date(value: str):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def load(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as fh:
        return {int(row["id"]): row for row in csv.DictReader(fh) if row.get("id", "").isdigit()}


def save(path: Path, state: dict[int, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for key in sorted(state):
            writer.writerow({col: state[key].get(col, "") for col in COLUMNS})


def plan(
    path: Path,
    candidates: list[dict],
    *,
    now: datetime,
    cooldown_hours: float = 6.0,
    abs_profit_change: float = 20_000_000,
    rel_profit_change: float = 0.10,
    roi_change: float = 0.02,
) -> list[dict]:
    """Return candidates needing mail; persist presence/pending before sending.

    First deployment establishes a no-backfill baseline, matching the previous
    Gmail policy. A failed send remains pending for the next healthy scan.
    Only call on a successfully completed, fresh market scan.
    """
    now = now.astimezone(timezone.utc)
    stamp = now.isoformat()
    current = {int(c["id"]): c for c in candidates}
    if not path.exists():
        state = {}
        for ident, c in current.items():
            state[ident] = {
                "id": str(ident), "active": "1", "pending": "0",
                "last_profit": str(float(c["profit"])),
                "last_roi": str(float(c["roi"])),
                "last_sent_at": stamp, "last_seen_at": stamp,
            }
        save(path, state)
        return []

    state = load(path)
    for ident, row in state.items():
        if ident not in current:
            row["active"] = "0"

    for ident, c in current.items():
        profit, roi = float(c["profit"]), float(c["roi"])
        if ident not in state:
            state[ident] = {
                "id": str(ident), "active": "1", "pending": "1",
                "last_profit": "0", "last_roi": "0",
                "last_sent_at": "", "last_seen_at": stamp,
            }
            continue
        row = state[ident]
        was_active = row.get("active") == "1"
        if not was_active:
            row["pending"] = "1"
        old_profit = float(row.get("last_profit") or 0)
        old_roi = float(row.get("last_roi") or 0)
        changed = (
            abs(profit - old_profit) >= abs_profit_change
            or abs(profit - old_profit) >= max(1, abs(old_profit)) * rel_profit_change
            or abs(roi - old_roi) >= roi_change
        )
        if changed:
            row["pending"] = "1"
        row["active"] = "1"
        row["last_seen_at"] = stamp

    save(path, state)
    ready = []
    for ident, c in current.items():
        row = state[ident]
        last = _date(row.get("last_sent_at", ""))
        cooled = last is None or now - last >= timedelta(hours=cooldown_hours)
        if row.get("pending") == "1" and cooled:
            ready.append(c)
    return ready


def acknowledge(path: Path, candidate: dict, *, now: datetime) -> None:
    """Advance dedupe state only after confirmed SMTP send."""
    state = load(path)
    ident = int(candidate["id"])
    row = state.get(ident)
    if row is None:
        raise RuntimeError(f"Market Gmail state missing for {ident}")
    row["last_profit"] = str(float(candidate["profit"]))
    row["last_roi"] = str(float(candidate["roi"]))
    row["last_sent_at"] = now.astimezone(timezone.utc).isoformat()
    row["last_seen_at"] = row["last_sent_at"]
    row["pending"] = "0"
    row["active"] = "1"
    save(path, state)
