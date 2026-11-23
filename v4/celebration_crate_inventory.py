"""One-time historical PLEX-crate candidate discovery from versioned EVE Ref SDE.

Defaults to metadata-only review; NOTHING is added automatically to BOXES.
Pass --download-once to fetch the entire archive temporarily (bounded existing
v4.catalog.fetch_archive). Regular V4 runs never call this file.

Output distinguishes manually approved 15, known nontradeable crates, unknown
quantity, and description hits requiring review. No market/ESI/mail side effects.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
import tempfile
from pathlib import Path

from v4.catalog import fetch_archive, REF_URL
from v4.celebration_crate_radar import BOXES

REGISTRY = Path(__file__).resolve().parent / "reference" / "celebration_crate_candidate_registry.json"
CRATE_NAME = re.compile(r"\b(crate|box|bundle|pack(?:age)?|gift|chest|cache|container)\b", re.I)
PLEX_TOKEN = re.compile(r"\bPLEX\b", re.I)
NO_TRADE = re.compile(r"(cannot|can't|not permitted|unable to|may not).{0,75}"
                      r"(trad|sell|contract)", re.I | re.S)
GUARANTEED = re.compile(
    r"(?:contains?|includes?|receive|rewarded with|comes with|includes the following items)"
    r"[\s\S]{0,210}?\b(\d[\d,]*)\s+PLEX\b", re.I)
NUMBER = re.compile(r"\b(\d[\d,]*)\s+PLEX\b", re.I)
MAY_DROP = re.compile(r"(chance|random|one of|can drop|may contain|possible|potentially)", re.I)


def english(field):
    if isinstance(field, str):
        return field
    if isinstance(field, dict):
        for key in ("en", "en-us", "en_US", "english"):
            if isinstance(field.get(key), str):
                return field[key]
    return ""


def known_registry(path=REGISTRY):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != 1 or not isinstance(data.get("entries"), list):
        raise RuntimeError("HISTORICAL_CRATE_REGISTRY_INVALID")
    rows = {int(e["type_id"]): e for e in data["entries"]}
    if len(rows) != len(data["entries"]):
        raise RuntimeError("HISTORICAL_CRATE_REGISTRY_DUPLICATE")
    if set(rows) & set(BOXES):
        raise RuntimeError("HISTORICAL_REGISTRY_OVERLAPS_APPROVED_BOXES")
    return rows


def analyze_type_rows(types, *, registry=None):
    """Pure classification; never infer confirmed tradeability from published."""
    registry = known_registry() if registry is None else registry
    if not isinstance(types, dict):
        raise RuntimeError("HISTORICAL_SDE_TYPES_NOT_DICT")
    found = []
    missing_in_sde = set(registry)
    seen = set()
    for raw_id, entry in types.items():
        try:
            tid = int(raw_id)
        except (TypeError, ValueError):
            continue
        if not isinstance(entry, dict):
            continue
        seen.add(tid)
        missing_in_sde.discard(tid)
        name = english(entry.get("name")) or english(entry.get("name_id"))
        description = english(entry.get("description")) or english(entry.get("description_id"))
        already = tid in BOXES
        curated = registry.get(tid)
        candidate = bool(CRATE_NAME.search(name))
        mentions = bool(PLEX_TOKEN.search(description))
        if not (already or curated is not None or (candidate and mentions)):
            continue
        no_trade = bool(NO_TRADE.search(description))
        amount_candidates = [int(v.replace(",", "")) for v in NUMBER.findall(description)]
        # This is ONLY an automated hint; descriptions aren't a validated
        # drop table and can include promotional prose or probabilities.
        first_amount = amount_candidates[0] if amount_candidates else None
        if already:
            status = "ACTIVE_APPROVED"
            benchmark = BOXES[tid][1]
        elif curated is not None:
            status = curated["classification"]
            benchmark = None
        elif no_trade:
            status = "DISCOVERED_NON_TRADEABLE"
            benchmark = None
        elif not mentions:
            status = "REVIEW_NO_PLEX_DESCRIPTION"
            benchmark = None
        elif MAY_DROP.search(description):
            status = "DISCOVERED_RANDOM_PLEX_CANDIDATE_REVIEW"
            benchmark = None
        elif GUARANTEED.search(description):
            status = "DISCOVERED_FIXED_PLEX_CANDIDATE_REVIEW"
            benchmark = None
        else:
            status = "DISCOVERED_PLEX_UNSPECIFIED_REVIEW"
            benchmark = None
        found.append({
            "type_id": tid, "name": name or (curated or {}).get("name") or "",
            "status": status, "active_scanner": already,
            "approved_plex_amount": benchmark, "description_plex_mentioned": mentions,
            "description_numeric_plex_hint": first_amount,
            "description_random_word": bool(MAY_DROP.search(description)),
            "description_nontradable_word": no_trade,
            "market_group_id": entry.get("market_group_id"),
            "published": entry.get("published"),
            "description_excerpt": description[:360],
            "source": f"https://everef.net/types/{tid}",
        })
    found.sort(key=lambda x:(x["status"], x["type_id"]))
    statuses = {}
    for row in found:
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
    return {
        "status": "SDE_CANDIDATES_NOT_AUTO_APPROVED",
        "source": REF_URL,
        "type_count_in_sde": len(types),
        "approved_in_scanner": len(BOXES),
        "manually_reviewed_exclusions_or_unknown": len(registry),
        "registered_ids_missing_from_archive": sorted(missing_in_sde),
        "status_counts": dict(sorted(statuses.items())),
        "entries": found,
        "safety": "Never promote by name or PLEX mention alone; verify actual content, physical tradeability and accessibility."
    }


def from_archive(path, *, min_types=10_000):
    """Read only types.json from official EVE Ref merged Reference Data."""
    with tarfile.open(path, "r:xz") as tar:
        src = tar.extractfile("types.json")
        if src is None:
            raise RuntimeError("HISTORICAL_SDE_TYPES_JSON_MISSING")
        types = json.load(src)
    if not isinstance(types,dict) or len(types) < min_types:
        raise RuntimeError("HISTORICAL_SDE_COVERAGE_TOO_SMALL")
    report = analyze_type_rows(types)
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    report["archive_sha256"] = h.hexdigest()
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, help="Already downloaded EVE Ref reference-data tar.xz")
    p.add_argument("--download-once", action="store_true", help="Explicit bounded download; temporary, no scheduled fetch")
    p.add_argument("--output", type=Path, help="Optional local JSON audit report")
    args = p.parse_args()
    if args.archive and args.download_once:
        p.error("--archive and --download-once are mutually exclusive")
    if not args.archive and not args.download_once:
        rows = known_registry()
        report = {
            "status": "MANUALLY_REVIEWED_REGISTRY_ONLY_NO_SDE_DISCOVERY",
            "approved_active_type_ids": sorted(BOXES),
            "extra_historical_registry": list(rows.values()),
            "note": "To independently discover additional PLEX mentions in historical types, use --download-once once."
        }
    elif args.archive:
        report = from_archive(args.archive)
    else:
        with tempfile.TemporaryDirectory(prefix="eve-crate-sde-") as d:
            archive = Path(d) / "reference-data-latest.tar.xz"
            fetch_archive(archive)
            report = from_archive(archive)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),
                               encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))


if __name__ == "__main__":
    main()
