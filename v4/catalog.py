"""Complete EVE Ref static item catalog, built once from ONE versioned bulk archive.

Never infer BPO/BPC instance identity from type_id: this catalog only tells us
whether the *type* is a blueprint. The actual contract's raw item metadata is
required to tell original from copy, and blueprint liquidation is blocked.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


REF_URL = "https://data.everef.net/reference-data/reference-data-latest.tar.xz"
DEFAULT_CACHE = Path(".cache/v4/reference/catalog.json.gz")
SCHEMA_VERSION = 1


class CatalogError(RuntimeError):
    pass


def _positive(value):
    try:
        v = float(value)
        return v if math.isfinite(v) and v > 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


@dataclass
class Catalog:
    items: dict[str, list]
    meta: dict

    def volume(self, type_id):
        row = self.items.get(str(int(type_id)))
        return row[0] if row else None

    def classification(self, type_id):
        row = self.items.get(str(int(type_id)))
        return row[1] if row else "unknown"

    def coverage(self, type_ids):
        ids = {int(x) for x in type_ids}
        known = sum(self.volume(t) is not None for t in ids)
        unknown = sorted(t for t in ids if self.volume(t) is None)
        blueprint_count = sum(self.classification(t) == "blueprint_type" for t in ids)
        return {"requested":len(ids), "known_volume":known, "missing_volume":len(unknown),
                "blueprint_types":blueprint_count, "unknown_sample":unknown[:30]}

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        try:
            with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as fh:
                json.dump({"schema":SCHEMA_VERSION, "meta":self.meta, "items":self.items},
                          fh, ensure_ascii=False, allow_nan=False, separators=(",",":"))
            os.replace(tmp,path)
        finally:
            tmp.unlink(missing_ok=True)

    @classmethod
    def load(cls,path):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            data=json.load(fh)
        if data.get("schema") != SCHEMA_VERSION or not isinstance(data.get("items"),dict):
            raise CatalogError("CATALOG_SCHEMA_MISMATCH")
        if data.get("meta",{}).get("type_count",0) != len(data["items"]):
            raise CatalogError("CATALOG_ROW_COUNT_MISMATCH")
        return cls(data["items"], data["meta"])


def from_archive(path, *, sha256=None, min_types=10000, min_blueprints=500) -> Catalog:
    """Reads actual EVE Ref types.json and blueprints.json from its tar.xz.

    Unlike the obsolete per-ID API method this has 2 archive reads, no 8000
    HTTP requests, and stable source hashes for each scan's audit.
    """
    try:
        with tarfile.open(path, "r:xz") as tar:
            typefile = tar.extractfile("types.json")
            bpfile = tar.extractfile("blueprints.json")
            if typefile is None or bpfile is None:
                raise CatalogError("BULK_ARCHIVE_MISSING_REQUIRED_TABLES")
            types = json.load(typefile)
            blueprints = json.load(bpfile)
    except (tarfile.TarError, KeyError, EOFError, json.JSONDecodeError) as exc:
        raise CatalogError("BULK_ARCHIVE_INVALID") from exc
    if not isinstance(types,dict) or len(types) < min_types:
        raise CatalogError("TOO_FEW_TYPES")
    if not isinstance(blueprints,dict) or len(blueprints) < min_blueprints:
        raise CatalogError("TOO_FEW_BLUEPRINTS")
    blueprint_ids = {str(int(k)) for k in blueprints}
    items = {}
    zero = 0
    for key,raw in types.items():
        if not isinstance(raw,dict):
            continue
        vol = _positive(raw.get("packaged_volume")) or _positive(raw.get("volume"))
        if vol is None:
            zero += 1
        items[str(int(key))] = [vol, "blueprint_type" if str(key) in blueprint_ids else "regular"]
    if len(items) < min_types:
        raise CatalogError("INCOMPLETE_CATALOG")
    return Catalog(items, {"source":REF_URL,"sha256":sha256,"schema":SCHEMA_VERSION,
        "built_at":datetime.now(timezone.utc).isoformat(),"type_count":len(items),
        "blueprint_count":len(blueprint_ids),"no_usable_volume":zero})


def fetch_archive(path, url=REF_URL):
    """Bounded, retryable bulk download; never accept truncated archive."""
    import requests  # Network dependency is optional for offline catalog tests.
    target = Path(path)
    target.parent.mkdir(parents=True,exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    last = None
    try:
        for attempt in range(3):
            digest=hashlib.sha256()
            total=0
            try:
                with requests.get(url,headers={"User-Agent":"V4-EVE-bulk-reference/1.0"},
                                  stream=True,timeout=(25,180)) as res:
                    res.raise_for_status()
                    expected=int(res.headers.get("content-length") or 0)
                    with tmp.open("wb") as fh:
                        for chunk in res.iter_content(1024*1024):
                            if not chunk:
                                continue
                            total += len(chunk)
                            if total>160_000_000:
                                raise CatalogError("ARCHIVE_TOO_LARGE")
                            digest.update(chunk)
                            fh.write(chunk)
                if total < 100_000 or (expected and total != expected):
                    raise CatalogError("TRUNCATED_ARCHIVE")
                os.replace(tmp,target)
                return digest.hexdigest()
            except (requests.RequestException, OSError, CatalogError) as exc:
                last=exc
                tmp.unlink(missing_ok=True)
        raise CatalogError("BULK_DOWNLOAD_FAILED: "+type(last).__name__) from last
    finally:
        tmp.unlink(missing_ok=True)


def ensure_catalog(cache=DEFAULT_CACHE, *, max_age_hours=168):
    """Weekly cache refresh, no silent stale fallback if network fails."""
    path=Path(cache)
    if path.exists():
        age=(datetime.now(timezone.utc).timestamp()-path.stat().st_mtime)/3600
        if 0 <= age <= max_age_hours:
            loaded=Catalog.load(path)
            return loaded
    with tempfile.TemporaryDirectory(prefix="eve-v4-catalog-") as d:
        archive=Path(d)/"reference-data-latest.tar.xz"
        sha=fetch_archive(archive)
        catalog=from_archive(archive,sha256=sha)
        catalog.save(path)
        return catalog
