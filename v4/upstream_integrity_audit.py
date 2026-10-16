"""Independent V4 market snapshot/ESI integrity audit (read-only).

The saved archive and ESI live views are NOT assumed to be simultaneous.
A missing order may be called confirmed missing ONLY if the archived region
and all ESI pages share the exact same HTTP Last-Modified timestamp. All
other differences are INCONCLUSIVE_VERSION_MISMATCH.

Uses only public ESI GET endpoints. No secrets, scheduler/database writes,
scan/mail side effects, or automatic downloads of replacement source archives.
"""
from __future__ import annotations

import argparse
import bz2
import csv
import json
import math
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from v4.source_freshness_audit import audit as source_age_audit, latest_run, utc

ESI = "https://esi.evetech.net/latest"
USER_AGENT = "EVE-V4-upstream-integrity-audit/1.0 (github.com/samson8964/chatgpt-eve)"
HEADERS = {"User-Agent": USER_AGENT, "X-Compatibility-Date": "2025-09-30",
           "Accept": "application/json"}


class EsiAuditError(RuntimeError):
    pass


def _stamp(value):
    value = utc(value)
    return value.replace(microsecond=0).isoformat() if value else None


def _minutes(then, now):
    a, b = utc(then), utc(now)
    return round((b - a).total_seconds()/60, 1) if a and b else None


def _sample_status(times: Counter, reference: str):
    ages=[]
    for key, n in times.items():
        age=_minutes(key,reference)
        if age is not None:
            ages.append((age,n))
    ages.sort()
    count=sum(n for _,n in ages)
    def q(p):
        if not count:
            return None
        mark=max(1,math.ceil(count*p))
        seen=0
        for age, n in ages:
            seen+=n
            if seen>=mark:
                return age
        return ages[-1][0]
    return {
        "timestamp_versions":len(times),
        "timestamps_newest_first":[{"http_last_modified_utc":k,"rows":n}
                                   for k,n in sorted(times.items(),reverse=True)[:5]],
        "cache_age_minutes":{"newest":q(0),"p50":q(.5),"p90":q(.9),"oldest":q(1)},
        "rows_older_60m":sum(n for age,n in ages if age>60),
        "rows_older_120m":sum(n for age,n in ages if age>120),
    }


def local_market_census(archive: Path, scan_started_at: str, *, compare_regions: set[int]):
    if not archive.exists():
        raise FileNotFoundError(str(archive))
    per=defaultdict(lambda: {"rows":0,"buy_orders":0,"sell_orders":0,
                             "missing_timestamp_rows":0,"time_versions":Counter(),
                             "duplicate_order_ids":0,"sampled_order_map":{}})
    full_seen=set()
    total=0
    missing_region=0
    malformed_order_id=0
    cross_region_duplicate=0
    with bz2.open(archive,"rt",encoding="utf-8",newline="") as fh:
        reader=csv.DictReader(fh)
        for required in ("region_id","order_id","http_last_modified",
                         "volume_remain","price","is_buy_order","type_id"):
            if required not in (reader.fieldnames or []):
                raise ValueError("MARKET_CSV_MISSING_FIELD:"+required)
        for row in reader:
            total+=1
            try:
                region=int(row["region_id"])
                order_id=int(row["order_id"])
                if region<=0 or order_id<=0:
                    raise ValueError()
            except (ValueError, TypeError, OverflowError):
                missing_region+=1
                continue
            stats=per[region]
            stats["rows"]+=1
            if str(row.get("is_buy_order","")).lower() in ("true","1","t"):
                stats["buy_orders"]+=1
            else:
                stats["sell_orders"]+=1
            ts=_stamp(row.get("http_last_modified"))
            if ts:
                stats["time_versions"][ts]+=1
            else:
                stats["missing_timestamp_rows"]+=1
            # Keep only 1.6M * (region, id) pairs in memory at most.
            if order_id in full_seen:
                cross_region_duplicate+=1
                stats["duplicate_order_ids"]+=1
            else:
                full_seen.add(order_id)
            if region in compare_regions:
                # Store essential order fields to prove more than just page counts.
                stats["sampled_order_map"][order_id]=(
                    str(row.get("type_id")),str(row.get("location_id")),
                    str(row.get("is_buy_order")).strip().lower() in ("true","1","t"),
                    str(row.get("volume_remain")),str(row.get("price")))
    public_regions={}
    for region,info in sorted(per.items()):
        public_regions[str(region)]={
            "rows":info["rows"],"buy_orders":info["buy_orders"],
            "sell_orders":info["sell_orders"],
            "missing_timestamp_rows":info["missing_timestamp_rows"],
            "duplicate_order_ids":info["duplicate_order_ids"],
            **_sample_status(info["time_versions"],scan_started_at)
        }
    return {
        "rows":total,"unique_orders":len(full_seen),
        "rows_missing_valid_region_or_id":missing_region,
        "duplicate_order_ids_global":cross_region_duplicate,
        "region_count_with_orders":len(public_regions),
        "regions":public_regions,
    }, {reg:x["sampled_order_map"] for reg,x in per.items() if reg in compare_regions}


def esi_fetch(session, path, *, params=None, sleep=time.sleep, max_tries=3):
    # Lazy optional dependency: offline CI and unit tests must not require
    # requests unless a real live ESI connection is requested.
    import requests
    url=ESI+path
    for attempt in range(max_tries):
        try:
            r=session.get(url,params=params,headers=HEADERS,timeout=(10,40))
        except requests.RequestException as exc:
            if attempt==max_tries-1:
                raise EsiAuditError("NETWORK_FAILURE:"+type(exc).__name__) from exc
            sleep(1.5*(attempt+1))
            continue
        if r.status_code in (420,429,500,502,503,504):
            wait=r.headers.get("Retry-After")
            try:
                seconds=max(1.0,float(wait)) if wait is not None else 2**attempt
            except (TypeError,ValueError):
                seconds=2**attempt
            if seconds>30:
                raise EsiAuditError("ESI_RETRY_AFTER_TOO_LONG:"+str(seconds))
            if attempt==max_tries-1:
                raise EsiAuditError("ESI_RETRY_EXHAUSTED:"+str(r.status_code))
            sleep(seconds)
            continue
        if r.status_code==404:
            return None,dict(r.headers),404
        if r.status_code!=200:
            raise EsiAuditError("ESI_HTTP_"+str(r.status_code))
        remaining=r.headers.get("X-Ratelimit-Remaining")
        if remaining is not None:
            try:
                if float(remaining)<500:
                    raise EsiAuditError("ESI_RATE_LIMIT_NEAR_EXHAUSTION")
            except ValueError:
                pass
        try:
            return r.json(),dict(r.headers),200
        except ValueError as exc:
            raise EsiAuditError("ESI_RESPONSE_NOT_JSON") from exc
    raise AssertionError("unreachable")


def probe_region(session, region: int, *, fetch=esi_fetch):
    payload, headers, status=fetch(session,f"/markets/{region}/orders/",
                                  params={"order_type":"all","page":1})
    if status==404:
        return {"region_id":region,"status":"NO_ESI_MARKET_ENDPOINT"}
    if not isinstance(payload,list):
        return {"region_id":region,"status":"MALFORMED_ESI_DATA"}
    try:
        pages=int(headers.get("X-Pages","1"))
        if not 1<=pages<=2000:
            raise ValueError()
    except (ValueError,TypeError):
        return {"region_id":region,"status":"BAD_X_PAGES"}
    return {"region_id":region,"status":"ESI_FIRST_PAGE_OK",
            "pages":pages,"first_page_orders":len(payload),
            "last_modified":_stamp(headers.get("Last-Modified")),
            "expires":headers.get("Expires"),
            "x_rate_remaining":headers.get("X-Ratelimit-Remaining"),
            "_first_page_data":payload}


def compare_region(session, region: int, local: dict, saved_ids: dict,
                   *, fetch=esi_fetch, sleep=time.sleep, pace=0.22,
                   max_pages=500):
    """Only exact same cache version and stable pagination allow missing IDs claim."""
    result=probe_region(session,region,fetch=fetch)
    result["archive_rows"]=local.get("rows",0)
    result["archive_http_last_modified_versions"]=local.get("timestamp_versions",0)
    result["archive_timestamp_rows"]=local.get("timestamps_newest_first",[])
    if result["status"]!="ESI_FIRST_PAGE_OK":
        return result
    pages=result["pages"]
    if pages>max_pages:
        result["verification"]="SKIPPED_PAGE_LIMIT"
        result["required_pages"]=pages
        return _hide_internal(result)
    page1_ts=result["last_modified"]
    ids={}
    page_version_changed=False
    duplicate_ids=0
    for page in range(1,pages+1):
        if page==1:
            items=result["_first_page_data"]
        else:
            if pace:
                sleep(pace)
            items,headers,status=fetch(session,f"/markets/{region}/orders/",
                                       params={"order_type":"all","page":page})
            if status!=200 or not isinstance(items,list):
                result["verification"]="INCONCLUSIVE_ESI_PAGE_ERROR"
                result["failed_page"]=page
                return _hide_internal(result)
            if _stamp(headers.get("Last-Modified")) != page1_ts:
                page_version_changed=True
            extra_pages=int(headers.get("X-Pages","1"))
            if extra_pages!=pages:
                page_version_changed=True
        for row in items:
            oid=row.get("order_id")
            if not isinstance(oid,int) or oid<=0:
                result["verification"]="INCONCLUSIVE_ESI_MALFORMED_ORDER"
                return _hide_internal(result)
            if oid in ids:
                duplicate_ids+=1
            ids[oid]=row
    result["esi_orders_total_rows"]=sum(1 for p in ids) + duplicate_ids
    result["esi_orders_unique"]=len(ids)
    result["duplicate_ids_esi"]=duplicate_ids
    result["page_version_changed"]=page_version_changed
    archive_stamps={v["http_last_modified_utc"]
                    for v in (local.get("timestamps_newest_first") or [])}
    # Require every local row's timestamp to be accounted for, not merely top 5.
    versions=local.get("timestamp_versions",0)
    comparable=(page1_ts is not None
                and versions==1 and len(archive_stamps)==1
                and page1_ts in archive_stamps
                and not page_version_changed and duplicate_ids==0
                and local.get("missing_timestamp_rows",0)==0
                and local.get("duplicate_order_ids",0)==0)
    result["same_esi_cache_generation_as_archive"]=comparable
    saved=set(saved_ids)
    esi=set(ids)
    result["archive_orders_not_in_esi_now"]=len(saved-esi)
    result["esi_orders_not_in_archive"]=len(esi-saved)
    result["overlap_order_ids"]=len(esi&saved)
    if comparable:
        # Equal cache timestamps but inconsistent order IDs means a genuine
        # archived-region discrepancy, not necessarily an EVE Ref scraper bug.
        result["verification"]=("MATCH_SAME_CACHE_GENERATION"
                                if saved==esi else "DISCREPANCY_SAME_CACHE_GENERATION")
        if saved==esi:
            # Price and remaining quantity must also match for the same generation.
            mismatched=0
            for oid,row in ids.items():
                old=saved_ids[oid]
                try:
                    if (int(old[0])!=int(row["type_id"]) or
                        int(old[1])!=int(row["location_id"]) or
                        old[2] != bool(row["is_buy_order"]) or
                        int(old[3])!=int(row["volume_remain"]) or
                        not math.isclose(float(old[4]),float(row["price"]),abs_tol=.000001)):
                        mismatched+=1
                except (ValueError,TypeError,KeyError):
                    mismatched+=1
            result["same_cache_order_details_differ"]=mismatched
            if mismatched:
                result["verification"]="DISCREPANCY_SAME_CACHE_GENERATION"
    else:
        result["verification"]="INCONCLUSIVE_VERSION_MISMATCH"
    return _hide_internal(result)


def _hide_internal(row):
    return {k:v for k,v in row.items() if not k.startswith("_")}


def run(root: Path, *, region_ids, probe_all=False, reconcile=True,
        fetch=esi_fetch, pace=.22, max_pages=500):
    folder,manifest=latest_run(root)
    stamp=manifest.get("started_at")
    archived=folder/"source"/"market_orders.csv.bz2"
    source_age=source_age_audit(root,deep=False)
    region_ids={int(i) for i in region_ids}
    census,saved_maps=local_market_census(archived,stamp,
                                         compare_regions=region_ids if reconcile else set())
    report={
        "run":folder.name,
        "audit_at_utc":datetime.now(timezone.utc).isoformat(),
        "scan_age_minutes_at_audit":_minutes(stamp,datetime.now(timezone.utc).isoformat()),
        "archive_market_upload_age_minutes_at_scan":source_age["sources"]["market_orders"]["upload_age_minutes_at_scan"],
        "archive_contract_upload_age_minutes_at_scan":source_age["sources"]["public_contracts"]["upload_age_minutes_at_scan"],
        "contract_scrape_end_age_minutes_at_scan":source_age["contract_archive_scrape"].get("scrape_end_age_minutes_at_scan"),
        "market_archive_global":{k:v for k,v in census.items() if k!="regions"},
        "region_cache_age_summary":census["regions"],
        "live_esi":{},
        "methodology":"A live ESI comparison is conclusive for order-ID and price equality ONLY if cache Last-Modified timestamps match exactly on every compared page and the saved region. Otherwise it is a time-shifted spot check, never proof of omissions.",
        "limitations":"ESI public regional orders do not include other players' private structure markets. Having all expected regions does not prove no orders were missing during initial upstream fetch."
    }
    import requests
    with requests.Session() as session:
        if probe_all:
            try:
                regions,_,status=fetch(session,"/universe/regions/")
                if status!=200 or not isinstance(regions,list):
                    raise EsiAuditError("ESI_REGION_LIST_NOT_AVAILABLE")
            except EsiAuditError as exc:
                # Preserve valuable offline evidence even if ESI is blocked.
                regions=[]
                report["live_esi"]["all_region_probe_error"]=str(exc)
            report["live_esi"]["esi_universe_region_ids_total"]=len(regions)
            probes=[]
            for rid in regions:
                rid=int(rid)
                try:
                    row=probe_region(session,rid,fetch=fetch)
                except EsiAuditError as exc:
                    row={"region_id":rid,"status":"ERROR","error":str(exc)}
                    # Stop on rate-limit/security backoff, don't hammer ESI.
                    if any(s in str(exc) for s in
                           ("RATE_LIMIT","RETRY_AFTER","ESI_RETRY_EXHAUSTED")):
                        probes.append(row)
                        break
                seen=rid in set(int(x) for x in census["regions"])
                row=_hide_internal(row)
                row["archive_has_any_orders"]=seen
                row["archive_rows"]=census["regions"].get(str(rid),{}).get("rows",0)
                row["archive_region_snapshot_age_minutes_p90"]=(
                    census["regions"].get(str(rid),{}).get("cache_age_minutes",{}).get("p90"))
                probes.append(row)
                time.sleep(pace)
            report["live_esi"]["region_probes"]=probes
            report["live_esi"]["potentially_missing_market_regions"]=[
                x["region_id"] for x in probes
                if x.get("status")=="ESI_FIRST_PAGE_OK"
                and x.get("first_page_orders",0)>0 and not x["archive_has_any_orders"]]
            report["live_esi"]["potentially_missing_regions_are_NOT_confirmed"]=True
        if reconcile:
            out=[]
            for rid in sorted(region_ids):
                try:
                    row=compare_region(session,rid,census["regions"].get(str(rid),{}),
                                       saved_maps.get(rid,{}),fetch=fetch,
                                       pace=pace,max_pages=max_pages)
                except EsiAuditError as exc:
                    row={"region_id":rid,"verification":"NETWORK_OR_ESI_ERROR",
                         "error":str(exc)}
                out.append(row)
            report["live_esi"]["region_order_id_reconciliation"]=out
    return report


def main():
    parser=argparse.ArgumentParser(description="Read-only V4 archived snapshot and independent ESI region audit")
    parser.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    parser.add_argument("--region",type=int,action="append",default=[],
                        help="ESI region ID to compare by all pages, e.g. 10000060 Delve")
    parser.add_argument("--probe-all-regions",action="store_true",
                        help="One ESI market page per region from ESI universe list")
    parser.add_argument("--no-reconcile",action="store_true",
                        help="Audit archive and optionally first-page-probe regions only")
    parser.add_argument("--max-pages",type=int,default=500,
                        help="Skip full regional reconciliation when ESI region requires more pages")
    parser.add_argument("--pace",type=float,default=.22,
                        help="Sleep between public ESI requests (default 0.22s)")
    parser.add_argument("--output",type=Path,default=None,
                        help="Optional JSON diagnostic output file; default stdout only")
    args=parser.parse_args()
    region_ids=args.region or [10000060]  # Default region: Delve
    results=run(args.data_root,region_ids=region_ids,
                probe_all=args.probe_all_regions,reconcile=not args.no_reconcile,
                pace=args.pace,max_pages=args.max_pages)
    blob=json.dumps(results,ensure_ascii=False,indent=2,allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(blob,encoding="utf-8")
        print("V4_INDEPENDENT_AUDIT_REPORT",args.output)
    else:
        print(blob)


if __name__=="__main__":
    main()
