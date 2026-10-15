"""Read-only source age/coverage audit for completed local V4 snapshots.

No network, credentials, database writes, scheduling or mail. Inspect the
newest recorded run and the source files already saved by V4. Distinguishes
artifact upload timestamps from underlying ESI HTTP last-modified timestamps.
"""
from __future__ import annotations

import argparse
import bz2
import csv
import json
import math
import tarfile
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

JITA = "60003760"
EXAMPLE_STATIONS = {"60003760":"Jita 4-4", "60008494":"Amarr", "60011866":"Dodixie"}


def utc(value):
    if value is None or str(value).strip() == "":
        return None
    raw = str(value).strip()
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        try:
            dt = parsedate_to_datetime(raw)
        except (TypeError, ValueError, IndexError):
            return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def minutes_since(start, event):
    a, b = utc(start), utc(event)
    return round((a-b).total_seconds()/60, 1) if a and b else None


def latest_run(root):
    runs = Path(root)/"runs"
    if not runs.exists():
        raise RuntimeError("V4_RUN_DIRECTORY_MISSING")
    for d in sorted((x for x in runs.iterdir() if x.is_dir()),
                    key=lambda x:x.name,reverse=True):
        p=d/"manifest.json"
        if not p.is_file():
            continue
        try:
            manifest=json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if manifest.get("status")=="SHADOW_RECORDED":
            return d,manifest
    raise RuntimeError("NO_COMPLETED_V4_RUN")


def catalog_sources(report, started_at):
    src=report.get("sources") or {}
    out={}
    for k in ("market_orders","public_contracts"):
        v=src.get(k) or {}
        out[k]={
            "status":v.get("status"),
            "file_upload_last_modified":v.get("last_modified"),
            "upload_age_minutes_at_scan":minutes_since(started_at,v.get("last_modified")),
            "index_age_hours_at_fetch":v.get("age_hours"),
            "archive_sha256":v.get("sha256"),
            "compressed_bytes":v.get("compressed_bytes"),
        }
    return out


def contract_scrape_meta(path,started_at):
    with tarfile.open(path,mode="r:bz2") as archive:
        members=[m for m in archive.getmembers()
                 if m.isfile() and m.name.rsplit("/",1)[-1]=="meta.json"]
        if len(members)!=1:
            return {"status":"META_MISSING_OR_DUPLICATE"}
        handle=archive.extractfile(members[0])
        if handle is None:
            return {"status":"META_UNREADABLE"}
        data=json.load(handle)
    if not isinstance(data,dict):
        return {"status":"META_INVALID"}
    return {
        "status":"OK",
        "datasource":data.get("datasource"),
        "scrape_start":data.get("scrape_start"),
        "scrape_end":data.get("scrape_end"),
        "scrape_end_age_minutes_at_scan":minutes_since(started_at,data.get("scrape_end")),
        "scrape_duration_minutes":minutes_since(data.get("scrape_end"),data.get("scrape_start")),
    }


def market_row_freshness(path,started_at):
    """Scan full archived CSV sequentially; no data sampled or mutated."""
    timestamps=Counter()
    region_rows=Counter()
    station_rows=Counter()
    total=missing_or_invalid=0
    with bz2.open(path,"rt",encoding="utf-8",newline="") as stream:
        rows=csv.DictReader(stream)
        for row in rows:
            total+=1
            reg=str(row.get("region_id") or "")
            if reg:
                region_rows[reg]+=1
            loc=str(row.get("location_id") or "")
            if loc in EXAMPLE_STATIONS:
                station_rows[loc]+=1
            stamp=row.get("http_last_modified")
            ts=utc(stamp)
            if ts:
                timestamps[ts.isoformat()]+=1
            else:
                missing_or_invalid+=1
    ages=[]
    started=utc(started_at)
    for stamp,count in timestamps.items():
        t=utc(stamp)
        if t and started:
            ages.append(((started-t).total_seconds()/60,count))
    ages.sort()
    def percentile(p):
        if not ages:
            return None
        cut=p*sum(n for _,n in ages)
        cumulative=0
        for age,n in ages:
            cumulative+=n
            if cumulative>=cut:
                return round(age,1)
        return round(ages[-1][0],1)
    old60=sum(n for age,n in ages if age>60)
    old120=sum(n for age,n in ages if age>120)
    return {
        "rows":total,
        "regions_represented":len(region_rows),
        "region_order_counts_min":min(region_rows.values(),default=None),
        "region_order_counts_max":max(region_rows.values(),default=None),
        "jita_and_other_npc_station_order_rows":
            {EXAMPLE_STATIONS[k]:station_rows[k] for k in EXAMPLE_STATIONS},
        "http_last_modified_unreadable_rows":missing_or_invalid,
        "esi_http_last_modified_age_minutes":{
            "newest":percentile(0),"p50_order_weighted":percentile(.5),
            "p90_order_weighted":percentile(.9),
            "oldest":percentile(1),
            "rows_older_than_60m":old60,
            "rows_older_than_120m":old120,
        },
        "note":"HTTP cache modified timestamps are not individual trade timestamps.",
    }


def audit(root: Path, *, deep: bool=False):
    folder, manifest=latest_run(root)
    full=json.loads((folder/"full_market_report.json").read_text(encoding="utf-8"))
    source_dir=folder/"source"
    start=manifest.get("started_at")
    sources=catalog_sources(full,start)
    previous=[]
    for d in sorted((x for x in (Path(root)/"runs").iterdir()
                     if x.is_dir() and x.name < folder.name),
                    key=lambda d:d.name,reverse=True):
        f=d/"full_market_report.json"
        if f.exists() and (d/"manifest.json").exists():
            try:
                old=json.loads(f.read_text(encoding="utf-8"))
            except (OSError,ValueError):
                continue
            previous.append((d.name,old.get("sources") or {}))
            break
    if previous:
        prev_name,prev=previous[0]
        for k in sources:
            older=(prev.get(k) or {}).get("sha256")
            current=sources[k]["archive_sha256"]
            sources[k]["same_sha256_as_previous_run"]=bool(older and current and older==current)
        prev_run=prev_name
    else:
        prev_run=None
    outcome={
        "run":folder.name,"scan_started_at_utc":start,
        "full_census_result":full.get("overall"),
        "scope_note":"EVE Ref regional NPC/public-market data plus three explicitly authorized structure markets; only approved markets enter deep market profitability evaluation.",
        "sources":sources,
        "compared_previous_run":prev_run,
        "contract_archive_scrape":contract_scrape_meta(source_dir/"public_contracts.tar.bz2",start),
        "reported_market":full.get("market"),
        "reported_contracts":full.get("contracts"),
        "source_validation_limit":"Checks V4 input/download metadata; does NOT prove every upstream region/page/contract is complete, and does NOT verify live executable prices.",
    }
    if deep:
        outcome["market_esi_cache_timestamp_distribution"]=market_row_freshness(
            source_dir/"market_orders.csv.bz2",start)
    return outcome


def main():
    parser=argparse.ArgumentParser(description="Audit archived EVE Ref source freshness")
    parser.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    parser.add_argument("--deep",action="store_true",
                        help="Read the entire compressed market CSV; may take time.")
    args=parser.parse_args()
    print(json.dumps(audit(args.data_root,deep=args.deep),
                     ensure_ascii=False,indent=2,allow_nan=False))


if __name__=="__main__":
    main()
