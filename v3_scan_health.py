"""Per-lane scan outcomes: distinguish successful empty markets from failures/stale data."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

LATEST = Path("results/latest")
HEALTH = LATEST / "v3_scan_health.json"
LANES = {
    "v3-amarr-to-jita": ("V3_AMARR_OUTCOME", "v3_amarr_to_jita.csv"),
    "v3-dodixie-to-jita": ("V3_DODIXIE_OUTCOME", "v3_dodixie_to_jita.csv"),
    "v3-four-h-to-jita": ("V3_FOUR_H_MARKET_OUTCOME", "v3_four_h_to_jita.csv"),
    "v3-cj-to-jita": ("V3_CJ_MARKET_OUTCOME", "v3_cj_to_jita.csv"),
    "v3-jita-to-4h": ("V3_REVERSE_OUTCOME", "v3_jita_to_four_h.csv"),
}


def _inspect(outcome: str, path: Path) -> dict:
    if outcome != "success":
        return {"status": "failed", "rows": None, "outcome": outcome or "unknown"}
    if not path.is_file():
        return {"status": "missing_output", "rows": None, "outcome": outcome}
    try:
        frame = pd.read_csv(path)
        return {"status": "empty" if frame.empty else "ok", "rows": int(len(frame)), "outcome": outcome}
    except pd.errors.EmptyDataError:
        return {"status": "empty", "rows": 0, "outcome": outcome}
    except Exception as exc:
        return {"status": "invalid_output", "rows": None, "outcome": outcome, "error": type(exc).__name__}


def collect() -> dict:
    started_path = Path("results/state/last_scan_started_epoch.txt")
    try:
        started = int(started_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        started = 0
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "started_epoch": started,
        "run_id": os.getenv("GITHUB_RUN_ID", ""),
        "channels": {
            channel: _inspect(os.getenv(env, ""), LATEST / filename)
            for channel, (env, filename) in LANES.items()
        },
    }


def channel_healthy(channel: str, *, require_manifest: bool = False, max_age_hours: float = 2.0) -> bool:
    if channel not in LANES:
        return True
    if not HEALTH.exists():
        return not require_manifest
    try:
        health = json.loads(HEALTH.read_text(encoding="utf-8"))
        started = int(health.get("started_epoch") or 0)
        age = datetime.now(timezone.utc).timestamp() - started
        if started <= 0 or age < -120 or age > max_age_hours * 3600:
            return False
        return health["channels"][channel]["status"] in {"ok", "empty"}
    except (OSError, ValueError, KeyError, TypeError):
        return False


def main() -> None:
    LATEST.mkdir(parents=True, exist_ok=True)
    health = collect()
    HEALTH.write_text(json.dumps(health, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for channel, row in health["channels"].items():
        print(f"{channel}: {row['status']} rows={row['rows']} outcome={row['outcome']}")
        if row["status"] not in {"ok", "empty"}:
            print(f"::warning::V3 market lane degraded: {channel} status={row['status']}")


if __name__ == "__main__":
    main()
