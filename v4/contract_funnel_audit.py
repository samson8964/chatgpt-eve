"""Read-only V4 contract funnel, mail-suppression and crystal-screen audit.

No ESI calls, no mail, no scheduler, no DB updates, and NEVER calls
unified_review.make_review() (which updates first-seen history).
Compares *the same archived proofs* against the real contract mail gate,
then counterfactually disables ONLY the crystal group check.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from v4.contract_content_policy import (
    CRYSTAL_SHARE_BASIS, CRYSTAL_MAJORITY_SHARE,
    eligible_contract_research,
)

JITA = 60003760
VALUATION_BASIS = "JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE"
VALID_REASONS = {"LIVE_ORDER_AND_CONTRACT_NOT_REVALIDATED",
                 "BELOW_GATE_OR_STRESS"}
PROFIT_FLOOR = 50_000_000


def _read(path):
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("REPORT_NOT_OBJECT")
    return result


def _number(v):
    if isinstance(v,bool):
        return None
    try:
        n = float(v)
    except (ValueError, TypeError, OverflowError):
        return None
    return n if math.isfinite(n) else None


def _included_safe(proof):
    inc=proof.get("included_items")
    if not isinstance(inc,dict) or not inc:
        return False
    try:
        return all(str(k).isdigit() and int(v)>0 for k,v in inc.items())
    except (TypeError,ValueError,OverflowError):
        return False


def _basis_safe(proof):
    return (
        proof.get("valuation_location_id")==JITA and
        proof.get("destination_location")==JITA and
        proof.get("valuation_basis")==VALUATION_BASIS and
        isinstance(proof.get("contract_id"),int) and
        proof["contract_id"]>0 and
        proof.get("reason") in VALID_REASONS and
        proof.get("status")!="MAIL" and
        _included_safe(proof)
    )


def audit_folder(folder:Path):
    manifest=_read(folder/"manifest.json")
    full=_read(folder/"full_market_report.json")
    deep=_read(folder/"deep_shadow.json")
    if manifest.get("status")!="SHADOW_RECORDED":
        raise ValueError("NOT_COMPLETED_SCAN")
    crystal_required=deep.get("contract_crystal_screen_basis")==CRYSTAL_SHARE_BASIS
    reasons=Counter()
    gates=Counter()
    near_miss=Counter()
    numeric=0
    proof_total=0
    before_crystal=0
    after_crystal=0
    no_crystal_subset=0
    unknown_crystal_subset=0
    high_crystal_subset=0
    reason_qualified=0
    model_total=0
    top=[]
    raw_missing_net=0
    with (folder/"all_proofs.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            p=json.loads(line)
            if p.get("kind")!="contract":
                continue
            proof_total+=1
            reasons[str(p.get("reason") or "UNSPECIFIED")]+=1
            if p.get("model_candidate") is True:
                model_total+=1
            net=_number(p.get("net_profit"))
            roi=_number(p.get("roi"))
            stress=_number(p.get("stress_profit"))
            cost=_number(p.get("cost"))
            share=_number(p.get("energy_crystal_value_share"))
            if net is None:
                raw_missing_net+=1
            else:
                numeric+=1
                if net>=PROFIT_FLOOR:
                    gates["NET_GE_50M"]+=1
                if roi is not None and roi>=.10:
                    gates["ROI_GE_10_PERCENT"]+=1
                if stress is not None and stress>0:
                    gates["STRESS_POSITIVE"]+=1
                if stress is None:
                    gates["STRESS_UNAVAILABLE"]+=1
                if share is None:
                    gates["CRYSTAL_SHARE_UNKNOWN_WITH_NET"]+=1
                elif share>=CRYSTAL_MAJORITY_SHARE:
                    gates["CRYSTAL_SHARE_GE_HALF_WITH_NET"]+=1
            if not _basis_safe(p):
                continue
            reason_qualified+=1
            args=dict(net_profit=net,roi=roi,stress=stress,cost=cost)
            base=eligible_contract_research(**args,crystal_share=None,
                                            category_required=False)
            if not base:
                if net is not None and net >= PROFIT_FLOOR:
                    if roi is None or roi < .10:
                        near_miss["ROI_LT_10_PERCENT"]+=1
                    if stress is None:
                        near_miss["STRESS_NOT_CALCULABLE"]+=1
                    elif stress<=0:
                        near_miss["STRESS_NOT_POSITIVE"]+=1
                    if cost is None or cost<=0:
                        near_miss["COST_MISSING_OR_INVALID"]+=1
                continue
            before_crystal+=1
            if not crystal_required:
                allowed=eligible_contract_research(
                    **args,crystal_share=p.get("energy_crystal_value_share"),
                    category_required=False)
            else:
                allowed=eligible_contract_research(
                    **args,crystal_share=p.get("energy_crystal_value_share"),
                    category_required=True)
            if share is None:
                unknown_crystal_subset+=1
            elif share>=CRYSTAL_MAJORITY_SHARE:
                high_crystal_subset+=1
            else:
                no_crystal_subset+=1
            if allowed:
                after_crystal+=1
                top.append({"contract_id":p["contract_id"],
                            "net_profit_isk":net,
                            "roi":roi,
                            "stress_profit_isk":stress,
                            "crystal_share":share,
                            "source_location":p.get("source_location")})
    top.sort(key=lambda x:x["net_profit_isk"],reverse=True)
    declared=(deep.get("contract_approved_locations_examined") or 0)
    report={
        "run":folder.name,
        "contract_public_archive_rows":(full.get("contracts") or {}).get("contract_rows_total"),
        "approved_item_exchange_contract_rows":declared,
        "requested_item_contracts_excluded":deep.get("contract_requested_items_excluded"),
        "contracts_without_proof":declared-proof_total,
        "contract_proofs_found":proof_total,
        "contract_proof_count_eligible_scope":proof_total<=declared,
        "contract_reason_counts":dict(reasons.most_common()),
        "model_candidates":model_total,
        "contract_proofs_without_computed_net":raw_missing_net,
        "contract_proofs_with_computed_net":numeric,
        "numeric_gate_diagnostics":dict(gates),
        "valid_mail_proof_basis_count":reason_qualified,
        "count_qualifying_50m_roi_stress_BEFORE_crystal_filter":before_crystal,
        "count_qualifying_AFTER_crystal_filter":after_crystal,
        "rejected_only_by_crystal_filter":before_crystal-after_crystal,
        "among_basic_qualifiers_crystal_unknown":unknown_crystal_subset,
        "among_basic_qualifiers_crystal_majority":high_crystal_subset,
        "among_basic_qualifiers_crystal_below_half":no_crystal_subset,
        "crystal_filter_enabled":crystal_required,
        "basic_gate_near_misses_multi_label":dict(near_miss),
        "top_eligible_contracts":top[:8],
        "mail_coverage_gate":manifest.get("coverage_gate"),
        "mail_source_input_integrity":manifest.get("source_input_integrity"),
        "gmail_receipt_present":(folder.parent.parent/"mail-review"/"receipts"/(folder.name+".json")).is_file(),
        "mail_render_cap":10,
        "warning":"Full 50k contracts are not all item-exchange cash arbitrage proofs. Zero after crystal gate may mean classification missing, rather than economically invalid. Snapshot-only, not live executable.",
    }
    return report


def audit(root:Path, *, last:int=5):
    if not 1<=last<=24:
        raise ValueError("INVALID_RUN_COUNT")
    folders=sorted((root/"runs").iterdir(),key=lambda p:p.name,reverse=True)
    out=[]
    for p in folders:
        if not p.is_dir() or not (p/"manifest.json").exists():
            continue
        try:
            if _read(p/"manifest.json").get("status")!="SHADOW_RECORDED":
                continue
            out.append(audit_folder(p))
        except (ValueError,KeyError,OSError) as e:
            out.append({"run":p.name,"error":type(e).__name__+":"+str(e)})
        if len(out)>=last:
            break
    return {"run_count":len(out),"runs":out,"report_type":"READ_ONLY_CONTRACT_NO_MAIL_NO_NETWORK"}


def main():
    ap=argparse.ArgumentParser(description="Read-only V4 contract mail-funnel audit")
    ap.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    ap.add_argument("--runs",type=int,default=5)
    ap.add_argument("--output",type=Path,default=None)
    opts=ap.parse_args()
    result=audit(opts.data_root,last=opts.runs)
    if opts.output:
        opts.output.parent.mkdir(parents=True,exist_ok=True)
        opts.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),
                               encoding="utf-8")
    for item in result["runs"]:
        if "error" in item:
            print("RUN",item["run"],"ERROR",item["error"])
            continue
        print("RUN",item["run"],
              "all_contracts",item["contract_public_archive_rows"],
              "approved",item["approved_item_exchange_contract_rows"],
              "proofs",item["contract_proofs_found"],
              "valued",item["contract_proofs_with_computed_net"],
              "base_qualified",item["count_qualifying_50m_roi_stress_BEFORE_crystal_filter"],
              "after_crystal",item["count_qualifying_AFTER_crystal_filter"],
              "only_crystal_rejects",item["rejected_only_by_crystal_filter"],
              "crystal_unknown",item["among_basic_qualifiers_crystal_unknown"],
              "crystal_majority",item["among_basic_qualifiers_crystal_majority"],
              "gmail_receipt",item["gmail_receipt_present"])
    if result["runs"] and "error" not in result["runs"][0]:
        latest=result["runs"][0]
        print("LATEST_REASONS",json.dumps(latest["contract_reason_counts"],ensure_ascii=False))
        print("LATEST_GATES",json.dumps(latest["numeric_gate_diagnostics"],ensure_ascii=False))
        print("LATEST_BASIC_NEAR_MISS",json.dumps(latest["basic_gate_near_misses_multi_label"],ensure_ascii=False))
        print("LATEST_MAIL_COVERAGE_GATE",latest["mail_coverage_gate"])
    if opts.output:
        print("REPORT",opts.output)


if __name__=="__main__":
    main()
