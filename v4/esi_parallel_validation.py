"""ESI V4 one-shot *independent* public market census and EVE Ref comparison.

NEVER called from local_run, full_scan, local_service or any email sender.
Writes only DATA_ROOT/esi-parallel-validation/<UTC-run-id>/; existing V4
databases, raw source snapshots, scheduled tasks and mail are untouched.

Regions: public /universe/regions/. Orders: unauthenticated
/markets/{region}/orders/?order_type=all&page=N. Upwell station market orders
need authorization and are deliberately excluded from this public census.

Explicit 404 regions are recorded as unavailable, NOT silently treated as
verified empty. Official ESI X-Pages / Last-Modified checks are fail closed.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import os
import re
import sqlite3
import threading
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

ESI="https://esi.evetech.net/latest"
AGENT="EVE-V4-ESI-Parallel-Validator/1.0 (samson8964/chatgpt-eve; independent research)"
COMPAT_DATE="2026-10-01"
STATION_JITA=60003760
JSON_COLUMNS=("order_id","region_id","location_id","type_id","is_buy_order",
              "price","volume_remain","volume_total","min_volume","issued")
STORE_COLUMNS=("order_id","region_id","location_id","type_id","is_buy_order",
               "price","volume_remain")
_SCHEMA="""CREATE TABLE IF NOT EXISTS esi (
order_id INTEGER PRIMARY KEY, region_id INTEGER NOT NULL,
location_id INTEGER NOT NULL, type_id INTEGER NOT NULL,
is_buy_order INTEGER NOT NULL, price REAL NOT NULL,
volume_remain INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS everef (
order_id INTEGER PRIMARY KEY, region_id INTEGER,
location_id INTEGER NOT NULL, type_id INTEGER NOT NULL,
is_buy_order INTEGER NOT NULL, price REAL NOT NULL,
volume_remain INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS esi_location_idx ON esi(location_id);
CREATE INDEX IF NOT EXISTS ref_location_idx ON everef(location_id);"""


class ValidationError(RuntimeError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def _http_time(value):
    try:
        stamp=parsedate_to_datetime(value)
        if stamp.tzinfo is None:
            raise ValueError("naive HTTP date")
        return stamp.astimezone(timezone.utc)
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValidationError("ESI_MISSING_OR_INVALID_LAST_MODIFIED") from exc


def _row(record:dict, region:int) -> dict:
    required=("order_id","location_id","type_id","price","volume_remain",
              "volume_total","min_volume","is_buy_order")
    if not isinstance(record,dict) or any(k not in record for k in required):
        raise ValidationError("ESI_ORDER_MISSING_REQUIRED_FIELD")
    try:
        order=int(record["order_id"]); location=int(record["location_id"])
        typ=int(record["type_id"]); remaining=int(record["volume_remain"])
        total=int(record["volume_total"]); minimum=int(record["min_volume"])
        price=float(record["price"])
        buy=record["is_buy_order"]
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValidationError("ESI_ORDER_INVALID_FIELD") from exc
    if (order<=0 or location<=0 or typ<=0 or remaining<=0 or total<remaining
            or minimum<=0 or not math.isfinite(price) or price<=0
            or not isinstance(buy,bool)):
        raise ValidationError("ESI_ORDER_INVALID_VALUE")
    return {"order_id":order,"region_id":region,"location_id":location,
            "type_id":typ,"is_buy_order":int(buy),"price":price,
            "volume_remain":remaining}


class Api:
    def __init__(self, *, compatibility_date=COMPAT_DATE, min_interval=.2):
        self.compatibility_date=compatibility_date
        self.min_interval=min_interval
        self.lock=threading.Lock()
        self.next_allowed=0.0
        self.local=threading.local()
        self.counts=Counter()

    def _session(self):
        if not hasattr(self.local,"session"):
            session=requests.Session()
            session.headers.update({"User-Agent":AGENT,
                    "X-Compatibility-Date":self.compatibility_date,
                    "Accept":"application/json"})
            self.local.session=session
        return self.local.session

    def _pace(self):
        with self.lock:
            now=time.monotonic()
            wait=max(0,self.next_allowed-now)
            self.next_allowed=max(now,self.next_allowed)+self.min_interval
        if wait:
            time.sleep(wait)

    def request(self,path,params=None):
        last=None
        for attempt in range(1,5):
            self._pace()
            try:
                resp=self._session().get(ESI+path,params=params,
                                         timeout=(12,70))
                with self.lock:
                    self.counts[str(resp.status_code)]+=1
                headers={str(k).lower():v for k,v in resp.headers.items()}
                if resp.status_code==404:
                    return 404,None,headers
                if resp.status_code in (420,429,500,502,503,504):
                    try:
                        delay=int(headers.get("retry-after") or 0)
                    except (ValueError,TypeError):
                        delay=0
                    if attempt==4:
                        raise ValidationError(
                            f"ESI_HTTP_{resp.status_code}_RETRIES_EXHAUSTED")
                    time.sleep(min(180,max(2**attempt,delay)))
                    continue
                if resp.status_code!=200:
                    raise ValidationError(f"ESI_HTTP_{resp.status_code}")
                data=resp.json()
                return 200,data,headers
            except (requests.RequestException,ValueError) as exc:
                last=exc
                if attempt==4:
                    break
                time.sleep(2**attempt)
        raise ValidationError("ESI_CONNECTION_OR_JSON_FAILED:"+
                              type(last).__name__) from last


def _pages(headers):
    try:
        pages=int(headers["x-pages"])
    except (KeyError,TypeError,ValueError) as exc:
        raise ValidationError("ESI_X_PAGES_MISSING") from exc
    if not 1<=pages<=1500:
        raise ValidationError("ESI_X_PAGES_OUT_OF_RANGE")
    return pages


def fetch_region(api:Api, region:int, directory:Path):
    """Write per-region archive ONLY after complete, consistent pagination."""
    output=directory/f"{region}.jsonl.gz"
    temp=directory/f"{region}.jsonl.gz.part"
    info={"region_id":region,"status":"FAILED","pages":0,"orders":0,
          "last_modified":None,"cache_expires":None}
    try:
        # Retry a whole region, not a single page, if the 5-min cache rolls
        # between pages or the X-Pages count changed mid-census.
        for attempt in range(1,3):
            first_status,first,head=api.request(
                f"/markets/{region}/orders/",
                {"datasource":"tranquility","order_type":"all","page":1})
            if first_status==404:
                info.update(status="MARKET_ENDPOINT_404_UNVERIFIED",attempts=attempt)
                return info
            if not isinstance(first,list):
                raise ValidationError("ESI_MARKET_PAGE_NOT_LIST")
            pages=_pages(head)
            reference_stamp=head.get("last-modified")
            _http_time(reference_stamp)
            cache_expires=head.get("expires")
            # When Expires is already near, a multi-page scrape is likely to
            # roll over between pages. A strict mismatch will invalidate it.
            if cache_expires:
                try:
                    remaining=(_http_time(cache_expires)-datetime.now(timezone.utc)).total_seconds()
                    if remaining<10 and attempt<2:
                        time.sleep(max(1,min(15,10-remaining)))
                        continue
                except ValidationError:
                    pass
            count=0
            all_ids=set()  # ~1.6m total across ~110 regions; region-local only
            conflict=False
            with gzip.open(temp,"wt",encoding="utf-8",newline="") as stream:
                for page in range(1,pages+1):
                    if page==1:
                        rows,headers=first,head
                    else:
                        code,rows,headers=api.request(
                            f"/markets/{region}/orders/",
                            {"datasource":"tranquility","order_type":"all",
                             "page":page})
                        if code!=200:
                            conflict=True
                            info["error"]="ESI_PAGE_UNAVAILABLE_OR_404"
                            break
                    if (_pages(headers)!=pages or
                            headers.get("last-modified")!=reference_stamp):
                        conflict=True
                        info["error"]="ESI_PAGINATION_VERSION_MISMATCH"
                        break
                    if not isinstance(rows,list) or not rows:
                        conflict=True
                        info["error"]="ESI_PAGE_EMPTY"
                        break
                    for record in rows:
                        item=_row(record,region)
                        if item["order_id"] in all_ids:
                            conflict=True
                            info["error"]="ESI_ORDER_DUPLICATED_WITHIN_REGION"
                            break
                        all_ids.add(item["order_id"])
                        stream.write(json.dumps(item,separators=(",",":"))+"\n")
                        count+=1
                    if conflict:
                        break
            if conflict:
                temp.unlink(missing_ok=True)
                if attempt<2:
                    time.sleep(3)
                    continue
                raise ValidationError(info.get("error") or "ESI_PAGE_CONFLICT")
            os.replace(temp,output)
            return dict(info,status="COMPLETE",pages=pages,orders=count,
                        last_modified=reference_stamp,cache_expires=cache_expires,
                        attempts=attempt,error=None)
        raise ValidationError("ESI_REGION_RETRY_EXHAUSTED")
    except Exception as exc:
        info["error"]=str(exc)[:200]
        return info
    finally:
        temp.unlink(missing_ok=True)


def _insert_archive(con:sqlite3.Connection,path:Path):
    count=0
    batch=[]
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for line in f:
            r=json.loads(line)
            batch.append((r["order_id"],r["region_id"],r["location_id"],
                          r["type_id"],r["is_buy_order"],r["price"],
                          r["volume_remain"]))
            if len(batch)>=3000:
                con.executemany("INSERT INTO esi VALUES (?,?,?,?,?,?,?)",batch)
                count+=len(batch);batch=[]
        if batch:
            con.executemany("INSERT INTO esi VALUES (?,?,?,?,?,?,?)",batch)
            count+=len(batch)
    return count


def _read_reference(con, archive:Path):
    """Unmodified archived EVE Ref CSV; do not download a different generation."""
    count=0
    by_region=Counter()
    batch=[]
    with gzip.open(archive,"rt",encoding="utf-8",newline="") if archive.suffix==".gz" else \
         __import__("bz2").open(archive,"rt",encoding="utf-8",newline="") as f:
        reader=csv.DictReader(f)
        if not {"order_id","location_id","type_id","is_buy_order",
                "price","volume_remain"}.issubset(reader.fieldnames or []):
            raise ValidationError("EVEREF_REFERENCE_MISSING_REQUIRED_COLUMNS")
        for r in reader:
            try:
                rid=int(r["region_id"]) if r.get("region_id") else None
                oid=int(r["order_id"]);loc=int(r["location_id"])
                typ=int(r["type_id"]);price=float(r["price"])
                remaining=int(r["volume_remain"])
                flag=r["is_buy_order"].lower()
                if flag not in ("true","false","1","0"):
                    raise ValueError("reference side invalid")
                buy=int(flag in ("true","1"))
            except (ValueError,TypeError,OverflowError) as exc:
                raise ValidationError("EVEREF_REFERENCE_INVALID_ROW") from exc
            if min(oid,loc,typ,remaining)<=0 or not math.isfinite(price) or price<=0:
                raise ValidationError("EVEREF_REFERENCE_INVALID_VALUE")
            batch.append((oid,rid,loc,typ,buy,price,remaining))
            if rid is not None:
                by_region[rid]+=1
            if len(batch)>=3000:
                con.executemany("INSERT INTO everef VALUES (?,?,?,?,?,?,?)",batch)
                count+=len(batch);batch=[]
        if batch:
            con.executemany("INSERT INTO everef VALUES (?,?,?,?,?,?,?)",batch)
            count+=len(batch)
    return count,by_region


def _count(con,statement,params=()):
    return int(con.execute(statement,params).fetchone()[0])


def compare(con, region_results:list, ref_region_counts:dict):
    """Count exact order ID matches, price/quantity changes and Jita depth."""
    esi_count=_count(con,"SELECT COUNT(*) FROM esi")
    ref_count=_count(con,"SELECT COUNT(*) FROM everef")
    both=_count(con,"SELECT COUNT(*) FROM esi e INNER JOIN everef r USING(order_id)")
    differences=con.execute("""
      SELECT
        SUM(CASE WHEN ABS(e.price-r.price)>0.01 THEN 1 ELSE 0 END),
        SUM(CASE WHEN e.volume_remain<>r.volume_remain THEN 1 ELSE 0 END),
        SUM(CASE WHEN e.location_id<>r.location_id
                    OR e.type_id<>r.type_id
                    OR e.is_buy_order<>r.is_buy_order THEN 1 ELSE 0 END)
      FROM esi e JOIN everef r USING(order_id)""").fetchone()
    missing_regions=[]
    for region,number in ref_region_counts.items():
        if number>0 and not any(int(x["region_id"])==int(region) and
                x["status"]=="COMPLETE" for x in region_results):
            missing_regions.append(int(region))
    jita_esi=_count(con,"SELECT COUNT(*) FROM esi WHERE location_id=? AND is_buy_order=1",
                    (STATION_JITA,))
    jita_ref=_count(con,"SELECT COUNT(*) FROM everef WHERE location_id=? AND is_buy_order=1",
                    (STATION_JITA,))
    return {"esi_orders":esi_count,"everef_orders":ref_count,
            "matched_order_ids":both,
            "esi_only_order_ids":esi_count-both,
            "everef_only_order_ids":ref_count-both,
            "matched_price_changes":int(differences[0] or 0),
            "matched_remaining_volume_changes":int(differences[1] or 0),
            "matched_identity_changes":int(differences[2] or 0),
            "jita_buy_order_count_esi":jita_esi,
            "jita_buy_order_count_everef":jita_ref,
            "reference_regions_not_complete_on_esi":sorted(missing_regions),
            "interpretation":"Different snapshot times naturally produce order entry/exit, price and remaining-volume changes; differences are not automatic proof of missing coverage."}


def _latest_ref(root:Path):
    runs=root/"runs"
    if not runs.is_dir():
        return None,None
    for folder in sorted((x for x in runs.iterdir() if x.is_dir()),
                         reverse=True):
        path=folder/"source"/"market_orders.csv.bz2"
        if not path.is_file():
            continue
        try:
            manifest=json.loads((folder/"manifest.json").read_text("utf-8"))
            full=json.loads((folder/"full_market_report.json").read_text("utf-8"))
        except (OSError,ValueError):
            continue
        if manifest.get("status")!="SHADOW_RECORDED":
            continue
        timestamp=((full.get("sources") or {}).get("market_orders") or {}).get("last_modified")
        return path,{"run":folder.name,"last_modified":timestamp,
                     "archive_bytes":path.stat().st_size}
    return None,None


def run(root:Path, *, max_workers=3, max_regions=None, fetch_reference=True,
        fetcher=None, compatibility_date=COMPAT_DATE):
    root=Path(root)
    if max_workers<1 or max_workers>4:
        raise ValueError("MAX_WORKERS_OUT_OF_RANGE")
    if max_regions is not None and not (1<=max_regions<=200):
        raise ValueError("INVALID_MAX_REGIONS")
    name=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+uuid.uuid4().hex[:8]
    directory=root/"esi-parallel-validation"/name
    directory.mkdir(parents=True,exist_ok=False)
    parts=directory/"regions"
    parts.mkdir()
    report={
        "status":"STARTED","run":name,"started_at":utc_now(),
        "mode":"INDEPENDENT_ONE_SHOT_PUBLIC_ESI_SHADOW_NOT_LIVE",
        "live_mail_allowed":False,"read_only_existing_v4":True,
        "esi_url":ESI,"compatibility_date":compatibility_date,
        "workers":max_workers,"region_limit":max_regions,
        "authorized_structure_markets":"EXCLUDED_FROM_PUBLIC_ESI_AND_UNCHANGED_IN_V4",
        "comparison":None,
    }
    api=fetcher if fetcher is not None else Api(compatibility_date=compatibility_date)
    try:
        code,regions,headers=api.request(
            "/universe/regions/",{"datasource":"tranquility"})
        if code!=200 or not isinstance(regions,list) or not regions:
            raise ValidationError("ESI_REGION_DIRECTORY_NOT_AVAILABLE")
        if len(set(regions))!=len(regions) or any(
                not isinstance(x,int) or x<=0 for x in regions):
            raise ValidationError("ESI_INVALID_REGION_DIRECTORY")
        region_ids=sorted(regions)
        chosen=region_ids[:max_regions] if max_regions else region_ids
        report.update(universe_regions=len(region_ids),
                      attempted_regions=len(chosen),full_universe_requested=
                      (max_regions is None))
        results=[]
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            jobs={pool.submit(fetch_region,api,rid,parts):rid for rid in chosen}
            for job in as_completed(jobs):
                results.append(job.result())
                if len(results)%10==0 or len(results)==len(chosen):
                    successes=sum(x["status"]=="COMPLETE" for x in results)
                    errors=sum(x["status"]=="FAILED" for x in results)
                    print(f"ESI {len(results)}/{len(chosen)} regions "
                          f"complete={successes} errors={errors}",flush=True)
        results.sort(key=lambda x:x["region_id"])
        report["regions"]=results
        report["region_status_counts"]=dict(Counter(x["status"] for x in results))
        recorded_stamps=[
            _http_time(x["last_modified"]) for x in results
            if x["status"]=="COMPLETE" and x.get("last_modified")]
        if recorded_stamps:
            now=datetime.now(timezone.utc)
            oldest=min(recorded_stamps); newest=max(recorded_stamps)
            report["esi_cache_freshness"]={
                "oldest_last_modified":oldest.isoformat(),
                "newest_last_modified":newest.isoformat(),
                "oldest_age_minutes":round((now-oldest).total_seconds()/60,2),
                "newest_age_minutes":round((now-newest).total_seconds()/60,2),
                "span_minutes":round((newest-oldest).total_seconds()/60,2),
                "five_minute_rolling_cache_not_atomic_global_snapshot":True,
            }
        report["esi_pages"]=sum(x.get("pages") or 0 for x in results)
        report["esi_orders_reported"]=sum(x.get("orders") or 0 for x in results)
        report["failed_regions"]=[x["region_id"] for x in results
                                   if x["status"]=="FAILED"]
        report["unverified_404_regions"]=[x["region_id"] for x in results
                                   if x["status"]=="MARKET_ENDPOINT_404_UNVERIFIED"]
        complete=not report["failed_regions"]
        ref_path,ref_meta=_latest_ref(root) if fetch_reference else (None,None)
        if ref_path:
            report["reference"]=ref_meta
            try:
                stamp=datetime.fromisoformat(
                    str(ref_meta["last_modified"]).replace("Z","+00:00"))
                if stamp.tzinfo is not None:
                    report["reference"]["age_hours"]=round(
                        (datetime.now(timezone.utc)-stamp.astimezone(
                            timezone.utc)).total_seconds()/3600,3)
            except (ValueError,TypeError,OverflowError):
                pass
        else:
            report["reference"]={"status":"NO_PREVIOUS_COMPLETED_EVEREF_MARKET_ARCHIVE"}
        db=directory/"comparison.sqlite3"
        con=sqlite3.connect(db)
        try:
            con.executescript(_SCHEMA)
            con.execute("BEGIN")
            inserted=0
            for region in results:
                if region["status"]=="COMPLETE":
                    inserted+=_insert_archive(con,parts/f'{region["region_id"]}.jsonl.gz')
            con.commit()
            if inserted!=report["esi_orders_reported"]:
                raise ValidationError("ESI_IMPORTED_ORDER_COUNT_MISMATCH")
            report["esi_unique_orders"]=inserted
            if ref_path:
                con.execute("BEGIN")
                ref_count,regions_with_ref=_read_reference(con,ref_path)
                con.commit()
                report["reference"]["orders"]=ref_count
                report["comparison"]=compare(con,results,regions_with_ref)
                report["comparison"]["reference_market_region_count"]=len(regions_with_ref)
        finally:
            con.close()
        if not complete:
            report["status"]="INCOMPLETE_ESI_REGIONS"
        elif max_regions is not None:
            report["status"]="PARTIAL_REGION_TEST_ONLY"
        elif report["unverified_404_regions"]:
            missing=(report["comparison"] or {}).get(
                "reference_regions_not_complete_on_esi")
            report["status"]=(
                "PUBLIC_ESI_RETRIEVAL_COMPLETE_WITH_404_CAVEAT"
                if missing==[] else "PUBLIC_ESI_404_COVERAGE_UNVERIFIED")
        else:
            report["status"]="PUBLIC_ESI_REGIONS_COMPLETE"
        report["data_source_decision"]="DO_NOT_SWITCH_PRODUCTION"
    except Exception as exc:
        report["status"]="VALIDATION_FAILED"
        report["error"]=type(exc).__name__+":"+str(exc)[:300]
        report["data_source_decision"]="DO_NOT_SWITCH_PRODUCTION"
    finally:
        report["finished_at"]=utc_now()
        counts=getattr(api,"counts",None)
        if counts is not None:
            report["http_status_counts"]=dict(counts)
        destination=directory/"report.json"
        destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),
                               encoding="utf-8")
    return report,directory


def main():
    ap=argparse.ArgumentParser(description="One-shot ESI full-market parallel shadow validation (never changes V4 or mails)")
    ap.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    ap.add_argument("--workers",type=int,choices=(1,2,3,4),default=3)
    ap.add_argument("--max-regions",type=int,default=None,
                    help="For offline/limited smoke tests ONLY; omit for full universe")
    ap.add_argument("--no-reference",action="store_true")
    args=ap.parse_args()
    result,folder=run(args.data_root,max_workers=args.workers,
                       max_regions=args.max_regions,
                       fetch_reference=not args.no_reference)
    brief={k:result.get(k) for k in (
        "status","run","universe_regions","attempted_regions",
        "esi_pages","esi_unique_orders","region_status_counts",
        "failed_regions","unverified_404_regions","comparison",
        "data_source_decision","error")}
    print(json.dumps(brief,ensure_ascii=False,indent=2))
    print("REPORT",folder/"report.json")
    if result["status"] in ("VALIDATION_FAILED","INCOMPLETE_ESI_REGIONS"):
        raise SystemExit(2)


if __name__=="__main__":
    main()
