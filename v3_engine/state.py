from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping


STATE_VERSION = 1


def contract_fingerprint(
    contract_id: int,
    price: float,
    included: Mapping[int, int],
    requested: Mapping[int, int],
    start_location_id: int,
    expiry: str,
) -> str:
    payload = {
        "contract_id": int(contract_id),
        "price": round(float(price), 4),
        "included": sorted((int(k), int(v)) for k, v in included.items()),
        "requested": sorted((int(k), int(v)) for k, v in requested.items()),
        "start_location_id": int(start_location_id),
        "expiry": str(expiry or ""),
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_fingerprints(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text("utf-8"))
        if not isinstance(raw, dict):
            return {}
        data = raw.get("contracts", {})
        if not isinstance(data, dict):
            return {}
        return {int(k): str(v) for k, v in data.items()}
    except Exception:
        return {}


def save_fingerprints(path: Path, fingerprints: Mapping[int, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": STATE_VERSION,
        "contracts": {str(int(k)): str(v) for k, v in fingerprints.items()},
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), "utf-8")
    tmp.replace(path)
