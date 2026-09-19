from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode


def _root() -> Path | None:
    raw = os.getenv("EVE_RUN_CACHE_DIR", "").strip()
    if not raw:
        return None
    p = Path(raw)
    p.mkdir(parents=True, exist_ok=True)
    return p


def enabled() -> bool:
    return _root() is not None


def _is_cacheable_request(url: str) -> bool:
    u = str(url)
    if "/markets/" in u and ("/orders/" in u or "/history/" in u):
        return True
    # Manufacturing cost quotes are immutable enough within a single scan and the
    # same blueprint/run/factory tuple often appears in many competing contracts.
    return "api.everef.net/v1/industry/cost" in u


def _namespace(url: str) -> str:
    if "api.everef.net/v1/industry/cost" in url:
        return "industry_cost"
    if "/orders/" in url:
        return "jita_orders"
    if "/history/" in url:
        return "jita_history"
    return "other"


def _canonical_key(url: str, params: dict | None) -> str:
    items = sorted((str(k), str(v)) for k, v in (params or {}).items())
    raw = f"{url}?{urlencode(items)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _atomic_json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(value, fh, ensure_ascii=False, separators=(",", ":"))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def _update_stats(result: str, namespace: str, waited_seconds: float = 0.0) -> None:
    root = _root()
    if root is None:
        return
    lock_path = root / "stats.lock"
    stats_path = root / "stats.json"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            try:
                stats = json.loads(stats_path.read_text("utf-8")) if stats_path.exists() else {}
            except Exception:
                stats = {}
            stats.setdefault("requests", 0)
            stats.setdefault("hits", 0)
            stats.setdefault("misses", 0)
            stats.setdefault("writes", 0)
            stats.setdefault("lock_wait_seconds", 0.0)
            stats.setdefault("by_namespace", {})
            ns = stats["by_namespace"].setdefault(namespace, {"requests": 0, "hits": 0, "misses": 0, "writes": 0})
            stats["requests"] += 1
            ns["requests"] += 1
            if result == "hit":
                stats["hits"] += 1
                ns["hits"] += 1
            elif result == "miss":
                stats["misses"] += 1
                stats["writes"] += 1
                ns["misses"] += 1
                ns["writes"] += 1
            stats["lock_wait_seconds"] = round(float(stats.get("lock_wait_seconds", 0.0)) + max(0.0, waited_seconds), 6)
            stats["updated_at_epoch"] = time.time()
            # Statistics are diagnostic only. The lock protects concurrent writers;
            # avoid fsync-per-request because that would erase the speedup we are measuring.
            stats_path.write_text(json.dumps(stats, ensure_ascii=False, separators=(",", ":")), "utf-8")
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def cached_market_json(
    url: str,
    params: dict | None,
    fetcher: Callable[[], tuple[Any, Any]],
) -> tuple[Any, dict]:
    """Run-scoped single-flight cache for market reads and manufacturing quotes.

    Different scanner subprocesses share this directory. Per-key flock guarantees that
    the first process performs the network request and all later consumers reuse the
    exact payload and response headers from the same run.
    """
    root = _root()
    if root is None or not _is_cacheable_request(url):
        payload, headers = fetcher()
        return payload, dict(headers)

    namespace = _namespace(url)
    key = _canonical_key(url, params)
    data_path = root / "http" / namespace / f"{key}.json"
    lock_path = root / "locks" / f"{key}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    start_wait = time.monotonic()
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        waited = time.monotonic() - start_wait
        if data_path.exists():
            try:
                data = json.loads(data_path.read_text("utf-8"))
                _update_stats("hit", namespace, waited)
                return data["payload"], dict(data.get("headers") or {})
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

        try:
            payload, headers = fetcher()
            record = {
                "url": url,
                "params": params or {},
                "payload": payload,
                "headers": dict(headers),
                "fetched_at_epoch": time.time(),
            }
            _atomic_json_write(data_path, record)
            _update_stats("miss", namespace, waited)
            return payload, dict(headers)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def stats() -> dict:
    root = _root()
    if root is None:
        return {}
    p = root / "stats.json"
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:
        return {}
