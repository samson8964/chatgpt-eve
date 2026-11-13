"""Offline NPC-station high/low-security membership from CCP's Static Data Export.

Installation is EXPLICIT. Normal hourly V4 scans only read the small local
index and never download SDE or call ESI for thousands of locations.
Without this index, V4 retains its old limited contract scope and reports
NPC_CATALOG_NOT_INSTALLED (it never claims full NPC coverage).
"""
from __future__ import annotations
import argparse
import json
import math
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

VERSION = "3579973"  # CCP SDE release 2026-10-06; manually refresh as CCP publishes.
URL = (
    "https://developers.eveonline.com/static-data/tranquility/"
    f"eve-online-static-data-{VERSION}-jsonl.zip"
)
INDEX = Path("reference/npc-stations-high-low.json")
MAX_DOWNLOAD_BYTES = 450_000_000
MIN_NPC_STATIONS = 1000
MIN_SYSTEMS = 3000
SCHEMA = 1


def security_band(raw: float) -> str | None:
    """Match CCP's displayed-security convention: positive 0.0..0.4 lowsec.

    Game display rounds 0.45 to 0.5 and positive values below 0.05 to 0.1.
    Exact zero and negative values are nullsec, and MUST be excluded.
    """
    try:
        n = float(raw)
    except (ValueError, TypeError):
        return None
    if not math.isfinite(n):
        return None
    if n >= .45:
        return "HIGH"
    if 0 < n < .45:
        return "LOW"
    return None


def _member(archive: zipfile.ZipFile, suffix: str):
    names = [x for x in archive.namelist()
             if x.replace("\\", "/").rsplit("/", 1)[-1] == suffix]
    if len(names) != 1:
        raise RuntimeError("NPC_SDE_MISSING_OR_DUPLICATE_" + suffix)
    return names[0]


def compile_sde_zip(path: Path) -> dict:
    """Compile ALL station/system IDs; never guess security from station ID."""
    with zipfile.ZipFile(path) as z:
        systems: dict[int, tuple[float, int]] = {}
        with z.open(_member(z, "mapSolarSystems.jsonl")) as stream:
            for raw in stream:
                if not raw.strip():
                    continue
                o = json.loads(raw)
                sid = int(o["_key"])
                security = float(o["securityStatus"])
                region = int(o["regionID"])
                if not math.isfinite(security) or sid in systems:
                    raise RuntimeError("NPC_SDE_SYSTEM_INVALID")
                systems[sid] = (security, region)
        if len(systems) < MIN_SYSTEMS:
            raise RuntimeError("NPC_SDE_SYSTEMS_INCOMPLETE")

        stations: dict[str, dict] = {}
        total_npc = 0
        high = low = excluded_null = 0
        with z.open(_member(z, "npcStations.jsonl")) as stream:
            for raw in stream:
                if not raw.strip():
                    continue
                o = json.loads(raw)
                total_npc += 1
                station = int(o["_key"])
                system_id = int(o["solarSystemID"])
                if not 60_000_000 <= station < 70_000_000:
                    raise RuntimeError("NPC_SDE_STATION_ID_INVALID")
                if system_id not in systems:
                    raise RuntimeError("NPC_SDE_STATION_SYSTEM_MISSING")
                security, region = systems[system_id]
                band = security_band(security)
                if band is None:
                    excluded_null += 1
                    continue
                key = str(station)
                if key in stations:
                    raise RuntimeError("NPC_SDE_DUPLICATE_STATION")
                name = o.get("name")
                stations[key] = {
                    "system_id": system_id,
                    "region_id": region,
                    "security": security,
                    "band": band,
                    **({"name": name} if isinstance(name, str) and name.strip() else {}),
                }
                if band == "HIGH":
                    high += 1
                else:
                    low += 1
    if total_npc < MIN_NPC_STATIONS or high < 500 or low < 100:
        raise RuntimeError("NPC_SDE_STATION_COVERAGE_SUSPICIOUS")
    return {
        "schema": SCHEMA, "sde_version": VERSION, "sde_url": URL,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "npc_station_total": total_npc,
        "highsec_stations": high, "lowsec_stations": low,
        "nullsec_excluded": excluded_null,
        "stations": stations,
    }


def load_catalog(root: Path) -> dict | None:
    path = Path(root) / INDEX
    if not path.is_file():
        return None
    try:
        o = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("NPC_CATALOG_INVALID") from exc
    if (not isinstance(o, dict) or o.get("schema") != SCHEMA
            or not isinstance(o.get("stations"), dict)
            or len(o["stations"]) < MIN_NPC_STATIONS
            or o.get("highsec_stations", 0) < 500
            or o.get("lowsec_stations", 0) < 100):
        raise RuntimeError("NPC_CATALOG_INVALID")
    return o


def install(root: Path, *, sde_zip: Path | None = None) -> dict:
    """Fetch official ZIP once or accept user-downloaded ZIP. Atomic index write."""
    root = Path(root)
    target = root / INDEX
    target.parent.mkdir(parents=True, exist_ok=True)
    download = target.with_name("npc-sde-temporary.zip")
    remove_download = sde_zip is None
    if sde_zip is None:
        import requests
        try:
            with requests.get(URL, stream=True, timeout=(15, 180),
                              headers={"User-Agent":"EVE V4 NPC SDE catalog"}) as resp:
                resp.raise_for_status()
                total = 0
                with download.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=1<<20):
                        if chunk:
                            total += len(chunk)
                            if total > MAX_DOWNLOAD_BYTES:
                                raise RuntimeError("NPC_SDE_DOWNLOAD_TOO_LARGE")
                            f.write(chunk)
            sde_zip = download
        except Exception:
            download.unlink(missing_ok=True)
            raise
    try:
        built = compile_sde_zip(Path(sde_zip))
        temp = target.with_suffix(".json.part")
        try:
            temp.write_text(json.dumps(built, ensure_ascii=False,
                                       separators=(",", ":")), encoding="utf-8")
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)
    finally:
        if remove_download:
            download.unlink(missing_ok=True)
    return {key:built[key] for key in
            ("sde_version","npc_station_total","highsec_stations",
             "lowsec_stations","nullsec_excluded")} | {"index_path":str(target)}


def main():
    p = argparse.ArgumentParser(description="Install full NPC high/low-sec station catalog")
    p.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    p.add_argument("--install",action="store_true")
    p.add_argument("--sde-zip",type=Path,
                   help="Optional existing official CCP SDE JSONL ZIP, for offline use")
    args = p.parse_args()
    if args.install:
        print(json.dumps({"status":"NPC_CATALOG_INSTALLED",
                          **install(args.data_root,sde_zip=args.sde_zip)},
                         ensure_ascii=False,indent=2))
    else:
        existing = load_catalog(args.data_root)
        print(json.dumps({"status":"NPC_CATALOG_INSTALLED" if existing
                          else "NPC_CATALOG_NOT_INSTALLED",
                          **({k:existing[k] for k in
                              ("sde_version","npc_station_total",
                               "highsec_stations","lowsec_stations",
                               "nullsec_excluded")} if existing else {})},
                         ensure_ascii=False,indent=2))

if __name__ == "__main__":
    main()
