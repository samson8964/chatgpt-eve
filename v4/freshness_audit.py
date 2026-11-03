"""Audit actual V4 data freshness over multiple COMPLETED local scans.

Only reads existing manifests/source metadata/proofs; no ESI, network,
credentials, Windows task changes, or mail sending. SHA-256 differences
prove changed downloaded compressed source bytes; unchanged email candidates
alone do not prove reused data. Private ESI order BOOKS were not persisted,
so historic per-order private-market changes cannot be reconstructed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _read_json(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def _proof_summary(path: Path) -> dict:
    candidates = {}
    counts = {"market": 0, "contract": 0}
    if not path.is_file():
        return {"status": "NOT_RECORDED", "counts": counts, "candidate_keys": []}
    try:
        with path.open(encoding="utf-8") as source:
            for raw in source:
                if not raw.strip():
                    continue
                p = json.loads(raw)
                if not isinstance(p, dict):
                    return {"status": "INVALID_PROOF", "counts": counts,
                            "candidate_keys": []}
                kind = p.get("kind")
                if kind in counts:
                    counts[kind] += 1
                if p.get("model_candidate") is not True:
                    continue
                if kind == "market":
                    key = "M:" + str(p.get("source_location")) + ":" + str(p.get("type_id"))
                elif kind == "contract":
                    key = "C:" + str(p.get("contract_id"))
                else:
                    continue
                candidates[key] = p.get("profit") if kind == "market" else p.get("net_profit")
    except (OSError, ValueError, UnicodeError, TypeError):
        return {"status": "INVALID_PROOF", "counts": counts,
                "candidate_keys": []}
    return {"status": "PARSED", "counts": counts,
            "candidate_keys": sorted(candidates),
            "candidate_profits": candidates}


def _source_summary(raw: dict) -> dict:
    return {
        "status": raw.get("status"),
        "source_timestamp": raw.get("last_modified"),
        "age_hours_at_scan": raw.get("age_hours"),
        "sha256": raw.get("sha256"),
        "freshness_gate_hours": None,
    }


def inspect(root: Path, *, last: int = 12) -> dict:
    if not 1 <= last <= 48:
        raise ValueError("INVALID_HISTORY_LIMIT")
    run_dir = Path(root) / "runs"
    if not run_dir.is_dir():
        return {"status": "NO_LOCAL_RUNS"}
    completed = []
    for folder in sorted(run_dir.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        manifest = _read_json(folder / "manifest.json")
        if manifest.get("status") != "SHADOW_RECORDED":
            continue
        full = _read_json(folder / "full_market_report.json")
        deep = _read_json(folder / "deep_shadow.json")
        sources = full.get("sources") or {}
        market = _source_summary(sources.get("market_orders") or {})
        market["freshness_gate_hours"] = 2
        contracts = _source_summary(sources.get("public_contracts") or {})
        contracts["freshness_gate_hours"] = 3
        proof = _proof_summary(folder / "all_proofs.jsonl")
        health = deep.get("structure_health") or {}
        hashes = deep.get("private_market_order_book_sha256") or {}
        stations = {}
        for name in ("four_h", "cj", "o4t"):
            h = health.get(name) or {}
            stations[name] = {
                "status": h.get("status"),
                "order_rows": h.get("orders"),
                "_private_hash": hashes.get(name),
            }
        completed.append({
            "run": folder.name,
            "scan_status": manifest.get("status"),
            "full_census_status": full.get("overall"),
            "market": market,
            "contracts": contracts,
            "structures": stations,
            "model_market_keys": proof["candidate_keys"] if proof["status"] == "PARSED" else None,
            "market_proof_count": proof["counts"]["market"],
            "contract_proof_count": proof["counts"]["contract"],
            "_proof_status": proof["status"],
            "_profit_values": proof.get("candidate_profits") or {},
        })
        if len(completed) >= last:
            break
    completed.reverse()
    for idx, current in enumerate(completed):
        prev = completed[idx-1] if idx else None
        for source in ("market", "contracts"):
            a = current[source]
            b = (prev or {}).get(source) or {}
            a["changed_from_previous_run"] = (
                a["sha256"] != b.get("sha256")
                if a["sha256"] and b.get("sha256") else None)
            a["source_timestamp_changed"] = (
                a["source_timestamp"] != b.get("source_timestamp")
                if a["source_timestamp"] and b.get("source_timestamp") else None)
            # Keep prior hashes until ALL consecutive runs are compared.
            # Redact them only at the final output stage.
        for name, station in current["structures"].items():
            prior = (prev or {}).get("structures", {}).get(name) or {}
            a, b = station.get("_private_hash"), prior.get("_private_hash")
            station["book_fingerprint_recorded"] = bool(a)
            station["book_changed_from_previous_run"] = (
                a != b if a and b else None)
        if prev and (current["model_market_keys"] is not None and
                     prev["model_market_keys"] is not None):
            ids = set(current["model_market_keys"])
            old = set(prev["model_market_keys"])
            oldp, newp = prev["_profit_values"],current["_profit_values"]
            same = ids & old
            current["candidate_diff"] = {
                "new": len(ids-old),
                "gone": len(old-ids),
                "retained": len(same),
                "retained_profit_changed": sum(oldp.get(k) != newp.get(k)
                                               for k in same),
                "retained_profit_unchanged": sum(oldp.get(k) == newp.get(k)
                                                 for k in same),
            }
        else:
            current["candidate_diff"] = None
        current["model_candidate_keys"] = len(current["model_market_keys"] or [])
    # Keep preceding run evidence until every consecutive comparison is done.
    # Then strip all private/source fingerprints and detailed candidate IDs.
    for item in completed:
        for source in ("market","contracts"):
            item[source].pop("sha256", None)
        item.pop("model_market_keys",None)
        item.pop("_profit_values",None)
        item.pop("_proof_status",None)
        for station in item["structures"].values():
            station.pop("_private_hash", None)
    return {
        "status":"V4_FRESHNESS_HISTORY",
        "runs_compared":len(completed),
        "history":completed,
        "notes":[
            "EVE Ref public sources are pulled fresh every scan but may return the same version within their validity window.",
            "SHA changes indicate source compressed bytes differ; whether any particular opportunity changed is a separate comparison.",
            "Older private ESI market books lacked fingerprints; once two scans include fingerprints, book_changed_from_previous_run reports order-book differences.",
            "Same candidate IDs over successive scans do not prove stale source data.",
            "Per-run research mail receipts suppress duplicates only within a run, not across runs.",
        ],
    }


def main() -> None:
    parser=argparse.ArgumentParser(description="Compare source SHA/age and candidate changes across completed V4 scans")
    parser.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    parser.add_argument("--last",type=int,default=8)
    args=parser.parse_args()
    print(json.dumps(inspect(args.data_root,last=args.last),
                     ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
