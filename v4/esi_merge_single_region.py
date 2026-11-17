"""Join ONE independently revalidated missing ESI region with 113 saved ones.

This is an OFFLINE, read-only, shadow-only multi-epoch composite. It NEVER
relabels the failed original report as a complete same-timestamp census.
It creates a NEW report referencing immutable archives by validated run IDs,
preserving all source reports / SQLite and requiring zero production writes.
No market API, contract API, Gmail, scheduler or player-structure access.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sqlite3
import uuid
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

RUN_RE=re.compile(r"^\d{8}T\d{6}Z-[a-f0-9]{8}$")
FINISHED={"COMPLETE","EMPTY_MARKET_CONFIRMED"}
FIELDS={"order_id","region_id","location_id","type_id","price",
        "volume_remain","min_volume","range","volume_total","is_buy_order"}


class MergeError(RuntimeError):
    pass


def _report(root,run):
    if not isinstance(run,str) or not RUN_RE.fullmatch(run):
        raise MergeError("INVALID_VALIDATION_RUN_ID")
    directory=root/"esi-parallel-validation"/run
    path=directory/"report.json"
    if not path.is_file():
        raise MergeError("VALIDATION_REPORT_MISSING")
    report=json.loads(path.read_text(encoding="utf-8"))
    if report.get("run")!=run:
        raise MergeError("VALIDATION_RUN_ID_MISMATCH")
    return report,directory


def _utc(value):
    try:
        parsed=parsedate_to_datetime(str(value))
        if parsed.tzinfo is None:
            raise ValueError("missing time zone")
        return parsed.astimezone(timezone.utc)
    except (TypeError,ValueError,OverflowError) as exc:
        raise MergeError("INVALID_REGION_LAST_MODIFIED") from exc


def combine(root:Path,full_run:str,patch_run:str):
    """Return new multi-epoch report; archived orders are never recopied."""
    root=Path(root)
    if full_run==patch_run:
        raise MergeError("NEED_DISTINCT_VALIDATION_RUNS")
    original,original_dir=_report(root,full_run)
    patch,patch_dir=_report(root,patch_run)
    if (original.get("status")!="INCOMPLETE_ESI_REGIONS"
            or original.get("full_universe_requested") is not True
            or original.get("unverified_404_regions")
            or original.get("universe_regions")!=original.get("attempted_regions")
            or original.get("failed_regions") is None):
        raise MergeError("BASE_NOT_A_FAILED_FULL_REGION_CENSUS")
    failed=set(original.get("failed_regions") or [])
    if len(failed)!=1:
        raise MergeError("ONLY_SINGLE_REGION_RECOVERY_SUPPORTED")
    original_regions=original.get("regions") or []
    if (len(original_regions)!=original["universe_regions"]
            or len({r["region_id"] for r in original_regions})!=len(original_regions)
            or set(r["region_id"] for r in original_regions if
                   r["status"]=="FAILED")!=failed
            or any(r["status"] not in FINISHED|{"FAILED"}
                   for r in original_regions)):
        raise MergeError("INVALID_BASE_REGION_COVERAGE")
    region=next(iter(failed))
    patch_regions=patch.get("regions") or []
    if (patch.get("status")!="PARTIAL_REGION_TEST_ONLY"
            or patch.get("requested_region_ids")!=[region]
            or patch.get("full_universe_requested") is not False
            or patch.get("universe_regions")!=original["universe_regions"]
            or patch.get("attempted_regions")!=1
            or len(patch_regions)!=1
            or patch_regions[0]["region_id"]!=region
            or patch_regions[0]["status"] not in FINISHED):
        raise MergeError("PATCH_NOT_AN_INDEPENDENT_COMPLETE_SINGLE_REGION")
    if (not FIELDS.issubset(original.get("archive_execution_fields") or [])
        or not FIELDS.issubset(patch.get("archive_execution_fields") or [])):
        raise MergeError("EXECUTION_CRITICAL_FIELDS_NOT_ARCHIVED")
    archive=patch_dir/"regions"/f"{region}.jsonl.gz"
    if not archive.is_file():
        raise MergeError("PATCH_REGION_ARCHIVE_MISSING")
    origin_db=original_dir/"comparison.sqlite3"
    if not origin_db.is_file():
        raise MergeError("BASE_ID_INDEX_MISSING")
    # Validate all appended rows (including order-ID collision against the
    # original 1.5m-row index) before emitting any synthesized report.
    with closing(sqlite3.connect(
            f"file:{origin_db.resolve().as_posix()}?mode=ro",uri=True)) as con:
        if (con.execute("SELECT COUNT(*) FROM esi").fetchone()[0]
                !=original.get("esi_unique_orders")):
            raise MergeError("BASE_ID_INDEX_COUNT_INCONSISTENT")
        count=0
        seen=set()
        with gzip.open(archive,"rt",encoding="utf-8") as stream:
            for line in stream:
                raw=json.loads(line)
                if not isinstance(raw,dict) or not FIELDS.issubset(raw):
                    raise MergeError("PATCH_ORDER_FIELDS_INCOMPLETE")
                if int(raw["region_id"])!=region:
                    raise MergeError("PATCH_ORDER_REGION_MISMATCH")
                oid=int(raw["order_id"])
                if oid<=0 or oid in seen:
                    raise MergeError("PATCH_DUPLICATE_OR_INVALID_ORDER_ID")
                seen.add(oid)
                count+=1
                if con.execute("SELECT 1 FROM esi WHERE order_id=?",(oid,)).fetchone():
                    raise MergeError("PATCH_ORDER_ID_ALREADY_PRESENT_IN_BASE")
    if count!=int(patch_regions[0]["orders"]) or count!=patch.get("esi_unique_orders"):
        raise MergeError("PATCH_ORDER_COUNT_INCONSISTENT")
    if (sum(int(r["orders"]) for r in original_regions
            if r["status"] in FINISHED)!=original.get("esi_unique_orders")):
        raise MergeError("BASE_REGION_COUNT_INCONSISTENT")
    combined=[]
    for r in original_regions:
        if r["region_id"]==region:
            combined.append({**patch_regions[0],"archive_run":patch_run,
                             "repair_origin":"SEPARATE_OFFICIAL_ESI_CENSUS"})
        else:
            # Never allow a stale failed region file to masquerade as a
            # complete archive. All complete regional archives must exist.
            if not (original_dir/"regions"/f'{r["region_id"]}.jsonl.gz').is_file():
                raise MergeError("BASE_COMPLETE_REGION_ARCHIVE_MISSING")
            combined.append({**r,"archive_run":full_run})
    stamps=[_utc(r.get("last_modified")) for r in combined]
    oldest=min(stamps);newest=max(stamps)
    now=datetime.now(timezone.utc)
    final_run=now.strftime("%Y%m%dT%H%M%SZ")+"-"+uuid.uuid4().hex[:8]
    output_dir=root/"esi-parallel-validation"/final_run
    output_dir.mkdir(parents=True,exist_ok=False)
    combined_count=int(original["esi_unique_orders"])+count
    result={
        "status":"SHADOW_MULTI_EPOCH_REPAIRED_COVERAGE",
        "run":final_run,
        "created_at":now.isoformat(),
        "mode":"INDEPENDENT_OFFLINE_MULTI_EPOCH_SHADOW_ONLY",
        "full_universe_requested":True,
        "universe_regions":original["universe_regions"],
        "attempted_regions":len(combined),
        "regions":combined,
        "region_status_counts":dict(Counter(r["status"] for r in combined)),
        "failed_regions":[],
        "unverified_404_regions":[],
        "esi_unique_orders":combined_count,
        "esi_orders_reported":combined_count,
        "esi_exhausted_orders_excluded":(
            int(original.get("esi_exhausted_orders_excluded") or 0)
            +int(patch.get("esi_exhausted_orders_excluded") or 0)),
        "esi_pages":(
            int(original.get("esi_pages") or 0)
            +int(patch_regions[0].get("pages") or 0)),
        "archive_execution_fields":original["archive_execution_fields"],
        "reference":original.get("reference"),
        "comparison":None,
        "archive_lineage":{"base_run":full_run,"replacement_run":patch_run,
                           "replaced_region_id":region,
                           "no_existing_archives_modified":True},
        "esi_cache_freshness":{
            "oldest_last_modified":oldest.isoformat(),
            "newest_last_modified":newest.isoformat(),
            "oldest_age_minutes":round((now-oldest).total_seconds()/60,2),
            "newest_age_minutes":round((now-newest).total_seconds()/60,2),
            "span_minutes":round((newest-oldest).total_seconds()/60,2),
            "multi_epoch_not_atomic_global_snapshot":True},
        "same_v4_profit_model_executed":False,
        "live_mail_allowed":False,
        "read_only_existing_v4":True,
        "authorized_structure_markets":"EXCLUDED_UNCHANGED",
        "data_source_decision":"DO_NOT_SWITCH_PRODUCTION",
        "warning":"Explicitly stitched two independent ESI cache generations. Data are suitable for retrospective same-engine shadow research only; they are NOT a coherent same-time complete universe market snapshot, cannot be used to send alerts or to qualify a production source switch.",
    }
    destination=output_dir/"report.json"
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2),
                           encoding="utf-8")
    return result,destination


def main():
    p=argparse.ArgumentParser(description="Offline single-region ESI shadow reconstruction with immutable source archives; NO market requests")
    p.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    p.add_argument("--base-run",required=True)
    p.add_argument("--patch-run",required=True)
    args=p.parse_args()
    result,path=combine(args.data_root,args.base_run,args.patch_run)
    print(json.dumps({k:result[k] for k in (
        "status","run","esi_unique_orders","universe_regions",
        "region_status_counts","archive_lineage","esi_cache_freshness",
        "data_source_decision")},ensure_ascii=False,indent=2))
    print("REPORT",path)


if __name__=="__main__":
    main()
