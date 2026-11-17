"""Explicitly installed EVE Ref manufacturing recipes (no hourly network fetch).

EVE Ref blueprint JSON is maps of blueprint type -> activities.manufacturing,
containing material and product type/quantity maps. Cache only manufacturing
entries. Recipe schema is source-versioned and never fabricated.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import tarfile
import tempfile
from pathlib import Path

from v4.catalog import fetch_archive, REF_URL

RECIPE_CACHE=Path(".cache/v4/reference/manufacturing-recipes.json.gz")
SCHEMA=1


def _entries(raw):
    if isinstance(raw,dict):
        rows=raw.values()
    elif isinstance(raw,list):
        rows=raw
    else:
        return None
    result={}
    for row in rows:
        if not isinstance(row,dict):
            return None
        try:
            typ=int(row.get("type_id",row.get("typeID")))
            qty=int(row["quantity"])
        except (TypeError,ValueError,OverflowError,KeyError):
            return None
        if typ<=0 or qty<=0 or typ in result:
            return None
        prob=row.get("probability",1)
        if prob is not None and float(prob)!=1:
            return None  # stochastic invention/reactions, not fixed output
        result[str(typ)]=qty
    return result


def from_archive(path:Path):
    with tarfile.open(path,"r:xz") as archive:
        with archive.extractfile("blueprints.json") as fh:
            raw=json.load(fh)
    if not isinstance(raw,dict) or len(raw)<500:
        raise ValueError("BLUEPRINT_REFERENCE_DATA_INCOMPLETE")
    recipes={}
    invalid=0
    for typ,blueprint in raw.items():
        if not isinstance(blueprint,dict):
            continue
        act=(blueprint.get("activities") or {}).get("manufacturing")
        if not isinstance(act,dict):
            continue
        materials=_entries(act.get("materials"))
        products=_entries(act.get("products"))
        if not materials or not products:
            invalid+=1
            continue
        if len(products)!=1:
            invalid+=1
            continue
        try:
            bp=int(typ)
            duration=int(act.get("time") or 0)
        except (ValueError,TypeError,OverflowError):
            continue
        if bp<=0 or duration<=0:
            invalid+=1
            continue
        recipes[str(bp)]={"materials":materials,"products":products,
                           "time_seconds":duration}
    if len(recipes)<500:
        raise ValueError("TOO_FEW_MANUFACTURING_RECIPES")
    return {"schema":SCHEMA,"source":REF_URL,
            "manufacturing_recipes":recipes,"unsupported_entries":invalid}


def load(path:Path=RECIPE_CACHE):
    if not Path(path).is_file():
        return None
    with gzip.open(path,"rt",encoding="utf-8") as fh:
        item=json.load(fh)
    if item.get("schema")!=SCHEMA or not isinstance(item.get("manufacturing_recipes"),dict):
        raise RuntimeError("BLUEPRINT_RECIPE_CACHE_INVALID")
    return item


def install(path:Path=RECIPE_CACHE):
    target=Path(path)
    with tempfile.TemporaryDirectory(prefix="eve-v4-manufacturing-") as temp:
        archive=Path(temp)/"reference.tar.xz"
        sha=fetch_archive(archive)
        records=from_archive(archive)
    records["archive_sha256"]=sha
    target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_suffix(target.suffix+".part")
    try:
        with gzip.open(tmp,"wt",encoding="utf-8") as fh:
            json.dump(records,fh,separators=(",",":"))
        os.replace(tmp,target)
    finally:
        tmp.unlink(missing_ok=True)
    return {"status":"RECIPES_INSTALLED","manufacturing_recipes":len(records["manufacturing_recipes"]),
            "unsupported":records["unsupported_entries"]}


def main():
    ap=argparse.ArgumentParser(description="Install V4 blueprint manufacturing recipes explicitly, not in hourly scan")
    ap.add_argument("--install",action="store_true")
    ap.add_argument("--status",action="store_true")
    opts=ap.parse_args()
    if opts.install:
        print(json.dumps(install(),ensure_ascii=False))
    else:
        item=load()
        print(json.dumps({"status":"INSTALLED" if item else "NOT_INSTALLED",
                          "manufacturing_recipes":len(item["manufacturing_recipes"]) if item else 0},ensure_ascii=False))


if __name__=="__main__":
    main()
