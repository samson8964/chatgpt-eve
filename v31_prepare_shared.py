from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import requests

from scanner_source import (
    DATA,
    MARKET_ORDERS_INDEX,
    PUBLIC_CONTRACTS_INDEX,
    UA,
    download,
    latest_file,
)

STRUCTURE_ID = int(os.getenv("FOUR_H_STRUCTURE_ID", "1053970513596"))
WORKER_URL = os.getenv("EVE_MARKET_WORKER_URL", "https://eve-contract-opener.99617224.workers.dev").rstrip("/")
API_KEY = os.getenv("EVE_MARKET_API_KEY", "")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_structure_orders_once() -> tuple[list[dict], str | None, int]:
    if not API_KEY:
        raise RuntimeError("Missing EVE_MARKET_API_KEY")
    page = 1
    pages = 1
    raw: list[dict] = []
    expires = None
    while page <= pages:
        r = requests.get(
            f"{WORKER_URL}/api/structure-market",
            params={"structure_id": STRUCTURE_ID, "page": page},
            headers={"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"},
            timeout=60,
        )
        try:
            data = r.json()
        except Exception:
            raise RuntimeError(f"Structure market HTTP {r.status_code}: {r.text[:500]}")
        if r.status_code != 200 or not data.get("ok"):
            raise RuntimeError(f"Structure market error HTTP {r.status_code}: {data}")
        pages = max(1, int(data.get("pages") or 1))
        expires = expires or data.get("expires")
        raw.extend(data.get("orders") or [])
        page += 1
    return raw, expires, pages


def _link_into_data(snapshot_path: Path, source_url: str) -> Path:
    DATA.mkdir(parents=True, exist_ok=True)
    link = DATA / Path(source_url).name
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(snapshot_path.resolve())
    return link


def _append_github_env(values: dict[str, str]) -> None:
    env_path = os.getenv("GITHUB_ENV", "").strip()
    if not env_path:
        return
    with open(env_path, "a", encoding="utf-8") as fh:
        for key, value in values.items():
            fh.write(f"{key}={value}\n")


def main() -> None:
    root = Path(os.getenv("EVE_V31_RUN_ROOT", ".run/v31")).resolve()
    snapshots = root / "snapshots"
    cache = root / "cache"
    logs = root / "logs"
    for p in (snapshots, cache, logs):
        p.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    print("V3.1 shared-source preparation")
    print("1) resolve public snapshot versions")
    c_url, c_modified = latest_file(PUBLIC_CONTRACTS_INDEX)
    m_url, m_modified = latest_file(MARKET_ORDERS_INDEX)

    c_path = snapshots / Path(c_url).name
    m_path = snapshots / Path(m_url).name

    print("2) download public contracts exactly once")
    if c_path.exists():
        c_path.unlink()
    t0 = time.monotonic()
    download(c_url, c_path)
    contract_seconds = time.monotonic() - t0

    print("3) download market orders exactly once")
    if m_path.exists():
        m_path.unlink()
    t0 = time.monotonic()
    download(m_url, m_path)
    market_seconds = time.monotonic() - t0

    # Existing scanners keep using DATA/basename. Symlinks make the shared immutable
    # run snapshot transparent while preventing every scanner from downloading again.
    c_link = _link_into_data(c_path, c_url)
    m_link = _link_into_data(m_path, m_url)

    print("4) read authenticated 4-H market exactly once")
    t0 = time.monotonic()
    four_h_orders, four_h_expires, four_h_pages = fetch_structure_orders_once()
    four_h_seconds = time.monotonic() - t0
    four_h_path = snapshots / "four_h_orders.json"
    four_h_path.write_text(json.dumps(four_h_orders, ensure_ascii=False, separators=(",", ":")), "utf-8")

    # Make the three run inputs read-only after creation.
    for path in (c_path, m_path, four_h_path):
        path.chmod(0o444)

    manifest = {
        "version": "3.1",
        "created_at_epoch": time.time(),
        "datasets": {
            "public_contracts": {
                "source_url": c_url,
                "last_modified": c_modified,
                "path": str(c_path),
                "data_link": str(c_link),
                "bytes": c_path.stat().st_size,
                "sha256": sha256_file(c_path),
                "download_seconds": round(contract_seconds, 3),
            },
            "market_orders": {
                "source_url": m_url,
                "last_modified": m_modified,
                "path": str(m_path),
                "data_link": str(m_link),
                "bytes": m_path.stat().st_size,
                "sha256": sha256_file(m_path),
                "download_seconds": round(market_seconds, 3),
            },
            "four_h_market": {
                "structure_id": STRUCTURE_ID,
                "path": str(four_h_path),
                "orders": len(four_h_orders),
                "pages": four_h_pages,
                "expires": four_h_expires,
                "sha256": sha256_file(four_h_path),
                "fetch_seconds": round(four_h_seconds, 3),
            },
        },
        "prepare_seconds": round(time.monotonic() - started, 3),
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")

    values = {
        "EVE_RUN_SNAPSHOT_MANIFEST": str(manifest_path),
        "EVE_RUN_4H_ORDERS_PATH": str(four_h_path),
        "EVE_RUN_4H_EXPIRES": str(four_h_expires or ""),
        "EVE_RUN_CACHE_DIR": str(cache),
        "EVE_V31_RUN_ROOT": str(root),
        "EVE_V31_ENABLED": "1",
    }
    _append_github_env(values)

    print(
        f"V3.1 shared sources ready: contracts={c_path.stat().st_size/1e6:.1f}MB "
        f"market={m_path.stat().st_size/1e6:.1f}MB 4H_orders={len(four_h_orders):,} "
        f"prepare={manifest['prepare_seconds']:.1f}s"
    )


if __name__ == "__main__":
    main()
