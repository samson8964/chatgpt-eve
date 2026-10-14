"""Source-backed, strictly non-actionable contract review from the latest local V4 scan.

Never invent prices or claim live ESI verification. This module has no network,
SMTP, OAuth, or Windows credential access and does not modify scan evidence.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

MAX_CANDIDATES = 12


def _safe_float(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("INVALID_V4_REPORT")
    return value


def make_review(root: Path, *, limit: int = MAX_CANDIDATES) -> dict:
    root = Path(root).resolve()
    runs = root / "runs"
    folders = sorted((p for p in runs.iterdir() if p.is_dir()), reverse=True)
    finished = None
    for folder in folders:
        manifest = _load_json(folder / "manifest.json")
        if manifest.get("status") == "SHADOW_RECORDED":
            finished = (folder, manifest)
            break
    if finished is None:
        raise RuntimeError("NO_COMPLETED_V4_SHADOW_RUN")
    folder, manifest = finished
    deep = _load_json(folder / "deep_shadow.json")
    if deep.get("status") != "SHADOW_ONLY_NO_LIVE_ALERTS":
        raise RuntimeError("NOT_A_SHADOW_AUDIT")
    if manifest.get("mail_enabled") is not False or manifest.get("ready_for_production") is not False:
        raise RuntimeError("UNSAFE_SCAN_MAIL_STATUS")
    count = Counter()
    leads = []
    observed = 0
    proof_path = folder / "all_proofs.jsonl"
    with proof_path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            proof = json.loads(line)
            if proof.get("kind") != "contract":
                continue
            observed += 1
            count[str(proof.get("reason") or "UNSPECIFIED")] += 1
            cid = proof.get("contract_id")
            profit = _safe_float(proof.get("net_profit"))
            roi = _safe_float(proof.get("roi"))
            stress = _safe_float(proof.get("stress_profit"))
            cost = _safe_float(proof.get("cost"))
            if not isinstance(cid, int) or cid <= 0:
                continue
            # Only candidates whose ordinary items have already passed the
            # complete snapshot buy-depth/value calculation may be listed.
            if not (profit is not None and roi is not None and
                    stress is not None and cost is not None and
                    profit > 0 and roi > 0 and stress > 0 and cost > 0):
                continue
            reason = str(proof.get("reason") or "")
            if reason not in ("LIVE_ORDER_AND_CONTRACT_NOT_REVALIDATED",
                              "BELOW_GATE_OR_STRESS"):
                continue
            if proof.get("status") == "MAIL":
                raise RuntimeError("UNSAFE_FORMAL_PROOF_IN_SHADOW")
            included = proof.get("included_items")
            if not isinstance(included, dict) or not included:
                continue
            if any(not str(k).isdigit() or int(v) <= 0
                   for k, v in included.items()):
                continue
            leads.append({
                "contract_id": cid,
                "contract_price": _safe_float(proof.get("contract_price")),
                "investment": cost,
                "net_profit_snapshot": profit,
                "roi_snapshot": roi,
                "stress_profit_snapshot": stress,
                "included_items": included,
                "source_location": proof.get("source_location"),
                "expires_at": str(proof.get("expires_at") or ""),
                "reason": reason,
                "review_tier": ("MODEL_CANDIDATE" if proof.get("model_candidate") is True
                                else "BELOW_FORMAL_THRESHOLD"),
                "live_verified": False,
                "actionable": False,
            })
    expected = int(deep.get("contract_jita_examined") or 0)
    if observed > expected:
        raise RuntimeError("CONTRACT_PROOF_COUNT_EXCEEDS_JITA_CONTRACTS")
    leads.sort(key=lambda row: (
        row["review_tier"] != "MODEL_CANDIDATE",
        -row["net_profit_snapshot"], -row["roi_snapshot"], row["contract_id"]))
    return {
        "report_type": "V4_CONTRACT_REVIEW_ONLY",
        "run_folder": folder.name,
        "finished_at": manifest.get("finished_at"),
        "coverage_gate": manifest.get("coverage_gate"),
        "source_input_integrity": manifest.get("source_input_integrity"),
        "structure_health": {k:(v or {}).get("status") for k,v in
                             (manifest.get("structure_health") or {}).items()},
        "sqlite_unique_proofs": manifest.get("sqlite_unique_proofs"),
        "contract_jita_examined": expected,
        "contract_proofs_audited": observed,
        "contract_rejection_reasons": dict(count.most_common(12)),
        "research_leads_total": len(leads),
        "research_leads": leads[:max(0, min(int(limit), 50))],
        "formal_verified_contracts": 0,
        "live_orders_rechecked": False,
        "live_contract_rechecked": False,
        "warning": "Snapshot research only; never place an order based on this email.",
        "mail_enabled_in_scanner": False,
    }
