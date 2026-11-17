"""Display-only localized names from the official CCP SDE JSONL export.

Explicit installation, no hourly network access, no changes to scan references.
If a translation is absent, retain the real English name; never display a raw ID.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path

URL = "https://developers.eveonline.com/static-data/eve-online-static-data-latest-jsonl.zip"
CACHE = Path("reference/mail-names.json.gz")
SCHEMA = 1
MAX_BYTES = 450_000_000


def clean(value):
    if not isinstance(value, str):
        return ""
    # Names are data, not native EVE/HTML markup. Strip control characters.
    return " ".join(re.sub(r"[\x00-\x1f\x7f<>&]", " ", value).split()).strip()


def localized(value):
    if isinstance(value, dict):
        return clean(value.get("zh")) or clean(value.get("en")) or clean(value.get("en-us"))
    return clean(value)


def roman(n):
    n = int(n)
    if not 1 <= n <= 100:
        raise ValueError("INVALID_CELESTIAL_INDEX")
    out = ""
    for value, label in ((100,"C"),(90,"XC"),(50,"L"),(40,"XL"),(10,"X"),
                         (9,"IX"),(5,"V"),(4,"IV"),(1,"I")):
        count,n = divmod(n,value)
        out += label*count
    return out


def _rows(z, filename):
    paths = [p for p in z.namelist() if p.rsplit("/",1)[-1] == filename]
    if len(paths) != 1:
        raise ValueError("SDE_MEMBER_MISSING_OR_AMBIGUOUS:"+filename)
    with z.open(paths[0]) as f:
        for raw in f:
            if raw.strip():
                yield json.loads(raw)


def compile_names(path):
    with zipfile.ZipFile(path) as z:
        types = {str(r["_key"]):localized(r.get("name"))
                 for r in _rows(z,"types.jsonl")}
        types = {k:v for k,v in types.items() if v}
        systems = {int(r["_key"]):localized(r.get("name"))
                   for r in _rows(z,"mapSolarSystems.jsonl")}
        corps = {int(r["_key"]):localized(r.get("name"))
                 for r in _rows(z,"npcCorporations.jsonl")}
        operations = {int(r["_key"]):localized(r.get("operationName"))
                      for r in _rows(z,"stationOperations.jsonl")}
        planets = {}
        for r in _rows(z,"mapPlanets.jsonl"):
            system = systems.get(int(r["solarSystemID"]))
            if system:
                planets[int(r["_key"])] = (localized(r.get("uniqueName"))
                                             or f'{system} {roman(r["celestialIndex"])}')
        moons = {}
        for r in _rows(z,"mapMoons.jsonl"):
            parent = planets.get(int(r["orbitID"]))
            if parent:
                moons[int(r["_key"])] = (localized(r.get("uniqueName"))
                                          or f'{parent} - 卫星 {roman(r["celestialIndex"])}')
        stations = {}
        for r in _rows(z,"npcStations.jsonl"):
            name = localized(r.get("name"))
            orbit = int(r["orbitID"])
            parent = planets.get(orbit) or moons.get(orbit)
            corp = corps.get(int(r["ownerID"]))
            operation = operations.get(int(r["operationID"]))
            if not name and parent and corp:
                if r.get("useOperationName") and not operation:
                    continue
                name = parent+" - "+corp+(" "+operation if r.get("useOperationName") else "")
            if name:
                stations[str(r["_key"])] = name
    if len(types)<10_000 or len(stations)<1_000:
        raise ValueError("SDE_NAME_COVERAGE_INCOMPLETE")
    return {"schema":SCHEMA,"source":URL,"types":types,"stations":stations}


def load(root):
    path=Path(root)/CACHE
    try:
        with gzip.open(path,"rt",encoding="utf-8") as f:
            value=json.load(f)
        if (value.get("schema")!=SCHEMA or not isinstance(value.get("types"),dict)
                or not isinstance(value.get("stations"),dict)):
            return {}
        return value
    except (OSError,ValueError,TypeError,AttributeError):
        return {}


def install(root, source=None):
    """Download once, compile and atomically replace ONLY the display cache."""
    target=Path(root)/CACHE
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="v4-mail-names-") as work:
        path=Path(source) if source else Path(work)/"sde.zip"
        if not source:
            import requests
            with requests.get(URL,stream=True,timeout=(20,180),
                              headers={"User-Agent":"EVE V4 localized mail reference"}) as r:
                r.raise_for_status()
                total=0
                with path.open("wb") as f:
                    for chunk in r.iter_content(1<<20):
                        total+=len(chunk)
                        if total>MAX_BYTES:
                            raise ValueError("SDE_DOWNLOAD_TOO_LARGE")
                        f.write(chunk)
        names=compile_names(path)
        temp=target.with_suffix(".part")
        try:
            with gzip.open(temp,"wt",encoding="utf-8") as f:
                json.dump(names,f,ensure_ascii=False,separators=(",",":"))
            os.replace(temp,target)
        finally:
            temp.unlink(missing_ok=True)
    return {"status":"MAIL_NAMES_INSTALLED","types":len(names["types"]),
            "stations":len(names["stations"]),
            "chinese_types":sum(bool(re.search(r"[\u3400-\u9fff]",n)) for n in names["types"].values())}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    p.add_argument("--install",action="store_true")
    p.add_argument("--sde-zip",type=Path)
    a=p.parse_args()
    if a.install:
        result=install(a.data_root,a.sde_zip)
    else:
        names=load(a.data_root)
        result={"status":"MAIL_NAMES_INSTALLED" if names else "MAIL_NAMES_NOT_INSTALLED",
                "types":len(names.get("types",{})),"stations":len(names.get("stations",{}))}
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    main()
