"""Read-only drilldown of why V4 rejected most contract proofs before valuation.

Reuses saved all_proofs.jsonl plus the currently cached item catalogue. Does
not access ESI, refresh cached reference data, send email or mutate scan state.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from v4.catalog import Catalog, DEFAULT_CACHE
from v4.source_freshness_audit import latest_run

CLASS_REJECT = "ITEM_CLASSIFICATION_UNVERIFIED_OR_BLUEPRINT"


def _read_json(path:Path):
    return json.loads(path.read_text(encoding="utf-8"))


def analyze(folder:Path,catalog:Catalog|None):
    report=_read_json(folder/"deep_shadow.json")
    tally=Counter()
    examples={name:[] for name in (
        "HAS_UNKNOWN_ITEM_TYPE","HAS_BLUEPRINT_ITEM_TYPE",
        "ALL_REGULAR_UNEXPECTED_CLASS_REJECT","NO_CATALOG_AVAILABLE",
        "NO_INCLUDED_ITEMS","BLUEPRINT_METADATA_UNKNOWN")}
    bp_copy_states=Counter()
    unknown_types=Counter()
    blueprint_types=Counter()
    profit_floor=50_000_000
    profit_roi=0
    profit_roi_stress=0
    profit_only=0
    numeric_contracts=0
    normal_net_positive=0
    net_gte_0_lt_50m=0
    loss_count=0
    reason_counts=Counter()
    with (folder/"all_proofs.jsonl").open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            row=json.loads(line)
            if row.get("kind")!="contract":
                continue
            reason=str(row.get("reason") or "UNKNOWN")
            reason_counts[reason]+=1
            if reason==CLASS_REJECT:
                inc=row.get("included_items")
                if not isinstance(inc,dict) or not inc:
                    category="NO_INCLUDED_ITEMS"
                elif catalog is None:
                    category="NO_CATALOG_AVAILABLE"
                else:
                    typs=[int(t) for t in inc if str(t).isdigit()]
                    unknown=[t for t in typs if catalog.classification(t)=="unknown"]
                    bp=[t for t in typs if catalog.classification(t)=="blueprint_type"]
                    if unknown:
                        category="HAS_UNKNOWN_ITEM_TYPE"
                        unknown_types.update(unknown)
                    elif bp:
                        category="HAS_BLUEPRINT_ITEM_TYPE"
                        blueprint_types.update(bp)
                    else:
                        category="ALL_REGULAR_UNEXPECTED_CLASS_REJECT"
                tally[category]+=1
                if len(examples[category])<6:
                    examples[category].append({
                        "contract_id":row.get("contract_id"),
                        "types_count":len(inc) if isinstance(inc,dict) else None,
                        "blueprint_metadata":row.get("contract_blueprint_evidence"),
                        "included_type_ids":list(inc)[:6] if isinstance(inc,dict) else [],
                    })
                meta=row.get("contract_blueprint_evidence") or {}
                for k,n in meta.items():
                    try:
                        bp_copy_states[k]+=int(n)
                    except (ValueError,TypeError):
                        pass
                if meta.get("UNKNOWN_BLUEPRINT",0):
                    tally["BLUEPRINT_METADATA_UNKNOWN"]+=1
                continue
            if row.get("net_profit") is None:
                continue
            try:
                net=float(row["net_profit"])
            except (ValueError,TypeError):
                continue
            numeric_contracts+=1
            if net>0:
                normal_net_positive+=1
            elif net<0:
                loss_count+=1
            if 0<=net<profit_floor:
                net_gte_0_lt_50m+=1
            if net>=profit_floor:
                profit_only+=1
                try:
                    roi=float(row.get("roi"))
                except (ValueError,TypeError):
                    continue
                if roi>=.10:
                    profit_roi+=1
                    try:
                        stress=float(row.get("stress_profit"))
                    except (ValueError,TypeError):
                        continue
                    if stress>0:
                        profit_roi_stress+=1
    catalogue_meta=(report.get("catalog_meta") or {})
    actual_meta=catalog.meta if catalog else {}
    return {
        "run":folder.name,
        "classification_rejects_expected":reason_counts[CLASS_REJECT],
        "classification_rejects_explained":sum(tally[n] for n in (
            "HAS_UNKNOWN_ITEM_TYPE","HAS_BLUEPRINT_ITEM_TYPE",
            "ALL_REGULAR_UNEXPECTED_CLASS_REJECT","NO_CATALOG_AVAILABLE",
            "NO_INCLUDED_ITEMS")),
        "classification_reject_categories":dict(tally),
        "blueprint_copy_metadata_item_counts":dict(bp_copy_states),
        "common_unknown_item_types":unknown_types.most_common(10),
        "common_blueprint_item_types":blueprint_types.most_common(10),
        "cached_catalog_present":catalog is not None,
        "scan_catalog_source_sha256":catalogue_meta.get("sha256"),
        "cached_catalog_source_sha256":actual_meta.get("sha256"),
        "catalogue_matches_scan_sha256":(
            (catalogue_meta.get("sha256")==actual_meta.get("sha256"))
            if catalogue_meta.get("sha256") and actual_meta.get("sha256") else None),
        "cash_valuation":{
            "normal_net_computed":numeric_contracts,
            "net_profit_positive":normal_net_positive,
            "net_profit_negative":loss_count,
            "net_profit_0_to_below_50m":net_gte_0_lt_50m,
            "net_profit_at_least_50m":profit_only,
            "net_50m_and_roi_10_percent":profit_roi,
            "net_50m_and_roi_10_percent_and_stress_positive":profit_roi_stress,
        },
        "examples":examples,
        "warning":"Classification groups are derived using current local catalog; source SHA mismatch prevents firm attribution to historical scan. Missing or mixed blueprint item states must not be valued as BPO at BPC prices.",
    }


def main():
    ap=argparse.ArgumentParser(description="Read-only V4 contract classification and near-miss diagnostic")
    ap.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    ap.add_argument("--runs",type=int,default=3)
    ap.add_argument("--output",type=Path,default=None)
    args=ap.parse_args()
    if args.runs<1 or args.runs>12:
        ap.error("runs must be 1..12")
    repo=Path(__file__).resolve().parent.parent
    catalog_file=repo/DEFAULT_CACHE
    catalog=Catalog.load(catalog_file) if catalog_file.is_file() else None
    runs=sorted([x for x in (args.data_root/"runs").iterdir()
                 if x.is_dir() and (x/"manifest.json").is_file()],
                key=lambda p:p.name,reverse=True)
    out=[]
    for folder in runs:
        manifest=_read_json(folder/"manifest.json")
        if manifest.get("status")!="SHADOW_RECORDED":
            continue
        out.append(analyze(folder,catalog))
        if len(out)>=args.runs:
            break
    result={"runs":out,"read_only":True,
            "current_catalog_file":str(catalog_file) if catalog else None}
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),
                               encoding="utf-8")
    for r in out:
        print("RUN",r["run"])
        print("CLASSIFICATION",json.dumps(r["classification_reject_categories"],ensure_ascii=False))
        print("BLUEPRINT_META",json.dumps(r["blueprint_copy_metadata_item_counts"],ensure_ascii=False))
        print("CASH_VALUATION",json.dumps(r["cash_valuation"],ensure_ascii=False))
        print("CATALOG_MATCH",r["catalogue_matches_scan_sha256"])
    if args.output:
        print("REPORT",args.output)


if __name__=="__main__":
    main()
