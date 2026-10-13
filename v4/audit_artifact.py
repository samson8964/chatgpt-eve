"""Offline integrity gate for quota-paused V4 shadow artifacts (never sends mail)."""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from v4.ingest import read_proofs


def audit(report_path: Path, proofs_path: Path) -> dict:
    report=json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("status") != "SHADOW_ONLY_NO_LIVE_ALERTS" or report.get("formal_candidates") != 0:
        raise ValueError("SHADOW_RELEASE_GATE_INVALID")
    expected=int(report["proof_count"])
    reasons=Counter()
    statuses=Counter()
    seen=set()
    models=0
    raw=hashlib.sha256()
    with proofs_path.open("rb") as fh:
        for line in fh:
            raw.update(line)
    for row in read_proofs(proofs_path):
        key=row["instance"]
        if key in seen:
            raise ValueError("DUPLICATE_PROOF_INSTANCE:"+key)
        seen.add(key)
        status=row.get("status")
        if status not in ("WATCH","RESEARCH"):
            raise ValueError("UNSAFE_SHADOW_STATUS:"+str(status))
        reason=row.get("reason")
        if not isinstance(reason,str) or not reason:
            raise ValueError("MISSING_PROOF_REASON:"+key)
        statuses[status]+=1
        reasons[reason]+=1
        models+=row.get("model_candidate") is True
    if len(seen)!=expected:
        raise ValueError("SHADOW_PROOF_COUNT_MISMATCH")
    if dict(reasons)!=report.get("reason_counts"):
        raise ValueError("SHADOW_REJECTION_FUNNEL_MISMATCH")
    if models!=report.get("model_candidates"):
        raise ValueError("SHADOW_MODEL_CANDIDATE_MISMATCH")
    return {"ok":True,"kind":"OFFLINE_ARTIFACT_INTEGRITY_ONLY",
        "run_id":report["run_id"],"proof_count":len(seen),
        "model_candidates":models,"status_counts":dict(statuses),
        "reason_counts":dict(reasons),"proofs_sha256":raw.hexdigest(),
        "sql_unique_proofs":None,"durable_ledger_accepted":False,
        "release_enabled":False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--report",default="v4_output/latest/deep_shadow.json")
    parser.add_argument("--proofs",default="v4_output/latest/all_proofs.jsonl")
    parser.add_argument("--output",default="v4_output/latest/artifact_integrity.json")
    args=parser.parse_args()
    result=audit(Path(args.report),Path(args.proofs))
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    main()
