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
SCHEMA_VERSION = 2


class CatalogError(RuntimeError):
    pass


def blueprint_instance_kind(copy_flag, runs=None):
    """BPC/BPO evidence from a *contract item*, not merely its shared type_id.

    If source metadata conflicts or is missing, return UNKNOWN and do not
    allow cash liquidation. A valid BPC uses is_blueprint_copy=true and runs
    >=0; a valid BPO uses is_blueprint_copy=false and runs=-1.
    """
    text = str(copy_flag).strip().lower()
    if isinstance(copy_flag, bool):
        text = "true" if copy_flag else "false"
    try:
        v = float(runs)
        r = int(v) if math.isfinite(v) and v.is_integer() else None
    except (TypeError, ValueError, OverflowError):
        r = None
    if text == "true" and r is not None and r >= 0:
        return "BPC"
    if text == "false" and r == -1:
        return "BPO"
    return "UNKNOWN_BLUEPRINT"


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

    def group_id(self, type_id):
        """Inventory group from EVE Ref, NOT a market category or type-ID range."""
        row = self.items.get(str(int(type_id)))
        if not row or len(row) < 3:
            return None
        group = row[2]
        return group if isinstance(group, int) and group > 0 else None

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
    groups_known = 0
    for key,raw in types.items():
        if not isinstance(raw,dict):
            continue
        vol = _positive(raw.get("packaged_volume")) or _positive(raw.get("volume"))
        if vol is None:
            zero += 1
        # EVE Ref reference-data keys are snake_case. Some historical archives
        # have the original CCP groupID spelling; support both, never infer.
        raw_group=raw.get("group_id",raw.get("groupID"))
        try:
            group=int(raw_group) if raw_group is not None else None
        except (TypeError,ValueError,OverflowError):
            group=None
        if group is not None and group > 0:
            groups_known += 1
        else:
            group=None
        items[str(int(key))] = [vol, "blueprint_type" if str(key) in blueprint_ids else "regular", group]
    if len(items) < min_types:
        raise CatalogError("INCOMPLETE_CATALOG")
    # Production catalogs MUST contain group metadata. Otherwise crystal
    # classification would silently pass unwanted contracts to users.
    if min_types >= 10_000 and groups_known < int(len(items)*.95):
        raise CatalogError("ITEM_GROUP_METADATA_INCOMPLETE")
    return Catalog(items, {"source":REF_URL,"sha256":sha256,"schema":SCHEMA_VERSION,
        "built_at":datetime.now(timezone.utc).isoformat(),"type_count":len(items),
        "blueprint_count":len(blueprint_ids),"no_usable_volume":zero,
        "inventory_group_known":groups_known})


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
            try:
                loaded=Catalog.load(path)
            except CatalogError as exc:
                # Old schema-1 cached volume+blueprint tables lack item groups.
                # Rebuild once from the full bulk archive; do NOT quietly reuse.
                if str(exc) != "CATALOG_SCHEMA_MISMATCH":
                    raise
            else:
                return loaded
    with tempfile.TemporaryDirectory(prefix="eve-v4-catalog-") as d:
        archive=Path(d)/"reference-data-latest.tar.xz"
        sha=fetch_archive(archive)
        catalog=from_archive(archive,sha256=sha)
        catalog.save(path)
        return catalog
