"""Read-only diagnosis of failed V4 combined Gmail + EVE digests.

Never uses SMTP, Cloudflare, ESI, keyring, secrets, networking, or scanner jobs.
Shows schema compatibility and precise *approved* failure codes. Does not
print contract titles, usernames, environment, full paths, or credentials.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from v4.unified_review import make_review

ALLOWED_ERROR_CODES = {
    "NO_COMPLETED_V4_SHADOW_RUN",
    "NOT_A_SHADOW_AUDIT",
    "REVIEW_REQUIRES_NEW_JITA_4_4_VALUATION_SCAN",
    "UNSAFE_SCAN_MAIL_STATUS",
    "CONTRACT_PROOF_COUNT_EXCEEDS_JITA_CONTRACTS",
    "UNSAFE_FORMAL_PROOF_IN_SHADOW",
    "UNIFIED_REVIEW_REQUIRES_SHADOW_REPORT",
    "UNIFIED_REVIEW_REQUIRES_FRESH_JITA_MARKET_SCAN",
    "UNIFIED_REVIEW_REQUIRES_FRESH_JITA_CONTRACT_SCAN",
    "UNVERIFIED_FORMAL_MARKET_MAIL_FORBIDDEN",
    "MARKET_PROOF_COUNT_MISMATCH",
}
PRICING = "JITA_4_4_BUY_DEPTH_SNAPSHOT"


def _safe_report(path: Path) -> dict:
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else {}
    except (ValueError, OSError, UnicodeError):
        return {}


def _scan_counts(path: Path) -> dict:
    kinds = Counter()
    statuses = Counter()
    if not path.is_file():
        return {"status": "MISSING"}
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    return {"status": "MALFORMED_ROW"}
                kinds[str(row.get("kind"))] += 1
                if row.get("status") == "MAIL":
                    statuses[str(row.get("kind"))] += 1
        return {"status": "PARSED", "market": kinds["market"],
                "contract": kinds["contract"],
                "unquarantined_mail_by_kind": dict(statuses)}
    except (OSError, UnicodeError, ValueError, TypeError):
        return {"status": "PROOFS_READ_ERROR"}


def inspect(root: Path) -> dict:
    runs = Path(root) / "runs"
    if not runs.is_dir():
        return {"status": "NO_RUNS_DIRECTORY"}
    folders = sorted((p for p in runs.iterdir() if p.is_dir()), reverse=True)
    finished = None
    for folder in folders:
        manifest = _safe_report(folder / "manifest.json")
        if manifest.get("status") == "SHADOW_RECORDED":
            finished = folder
            break
    if finished is None:
        return {"status": "NO_COMPLETED_V4_SHADOW_RUN"}
    manifest = _safe_report(finished / "manifest.json")
    deep = _safe_report(finished / "deep_shadow.json")
    proofs = _scan_counts(finished / "all_proofs.jsonl")
    summary = {
        "run": finished.name,
        "scan_status": manifest.get("status"),
        "coverage_gate": manifest.get("coverage_gate"),
        "source_input_integrity": manifest.get("source_input_integrity"),
        "contract_pricing_basis": deep.get("contract_pricing_basis"),
        "market_pricing_basis": deep.get("market_pricing_basis"),
        "expected_market_proofs": deep.get("market_proofs_examined"),
        "expected_contracts": deep.get("contract_approved_locations_examined"),
        "actual_proofs": proofs,
        "gmail_receipt_exists": (
            Path(root)/"mail-review"/"receipts"/(finished.name + ".json")).is_file(),
        "eve_receipt_exists": (
            Path(root)/"mail-review"/"eve-receipts"/(finished.name + ".json")).is_file(),
    }
    try:
        r = make_review(root)
        summary.update({
            "review": "READY",
            "market_leads": r.get("market_research_leads_total"),
            "contract_leads": r.get("contract_research_leads_total"),
        })
    except Exception as exc:
        reason = str(exc)
        summary.update({
            "review": "BLOCKED",
            "error_code": (reason if reason in ALLOWED_ERROR_CODES
                           else "UNCLASSIFIED_" + type(exc).__name__),
        })
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="V4 local read-only digest diagnosis")
    parser.add_argument("--data-root", type=Path, default=Path.home()/"EVE-V4-Data")
    args = parser.parse_args()
    print(json.dumps(inspect(args.data_root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
