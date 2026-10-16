"""Durable, audit-friendly first-discovery ordering for V4 research digests.

Only COMPLETE, already-recorded local SHADOW snapshots are indexed.
This metadata never influences candidate eligibility or the scan itself.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from v4.engine import Policy
from v4.contract_content_policy import eligible_contract_research, CRYSTAL_SHARE_BASIS

SCHEMA = 1
JITA = 60003760
INDEX = Path("mail-review/opportunity-first-seen.json")


def _run_time(name: str) -> str | None:
    try:
        d = datetime.strptime(name[:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return d.isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError):
        return None


def market_key(row: dict) -> str | None:
    """Station+SKU family; refreshing prices or quantities is NOT a new find."""
    try:
        source, typ = int(row["source_location"]), int(row["type_id"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if source <= 0 or typ <= 0 or source == JITA:
        return None
    return f"M:{source}:{typ}"


def contract_key(row: dict) -> str | None:
    try:
        ident = int(row["contract_id"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    return f"C:{ident}" if ident > 0 else None


def blueprint_key(row: dict) -> str | None:
    """A blueprint manufacturing lead has its own durable discovery identity."""
    try:
        cid=int(row["contract_id"])
        bp=int(row["blueprint_type_id"])
    except (KeyError,TypeError,ValueError,OverflowError):
        return None
    return f"B:{cid}:{bp}" if cid>0 and bp>0 else None


def _number(value):
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return n if math.isfinite(n) else None


def _discovered_key(proof: dict) -> str | None:
    """Only historically eligible research leads count as first discovery."""
    if proof.get("kind") == "market":
        if (proof.get("model_candidate") is True and
                proof.get("valuation_location_id") == JITA and
                proof.get("destination_location") == JITA and
                proof.get("valuation_basis") == "JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE"):
            return market_key(proof)
    elif proof.get("kind") == "blueprint_manufacturing":
        if (proof.get("model_candidate") is True and
            proof.get("status") == "WATCH" and
            proof.get("valuation_basis") ==
              "JITA_BUY_FINISHED_GOODS_JITA_SELL_MATERIALS_SNAPSHOT" and
            proof.get("facility_fee_status") ==
              "20_PERCENT_MATERIAL_COST_RESERVE_NOT_FACILITY_VERIFIED"):
            return blueprint_key(proof)
    elif proof.get("kind") == "contract":
        if (proof.get("valuation_location_id") != JITA or
                proof.get("destination_location") != JITA or
                proof.get("valuation_basis") != "JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE" or
                proof.get("reason") not in ("LIVE_ORDER_AND_CONTRACT_NOT_REVALIDATED",
                                            "BELOW_GATE_OR_STRESS")):
            return None
        # Apply the same contract gates used by the Gmail/game-mail reader.
        # Older proof rows without a crystal screen cannot be established as
        # eligible under the new policy; do not backdate their discovery.
        if proof.get("energy_crystal_share_verified") is not True:
            return None
        if not eligible_contract_research(
                net_profit=_number(proof.get("net_profit")),
                roi=_number(proof.get("roi")),
                stress=_number(proof.get("stress_profit")),
                cost=_number(proof.get("cost")),
                crystal_share=proof.get("energy_crystal_value_share"),
                category_required=True,
                partial_mode=(proof.get("partial_liquidation_basis") ==
                    "JITA_CREDITED_REGULAR_BUY_DEPTH_IGNORED_CARGO_ZERO")):
            return None
        included = proof.get("included_items")
        if not isinstance(included, dict) or not included:
            return None
        try:
            if not all(str(k).isdigit() and int(v) > 0 for k, v in included.items()):
                return None
        except (ValueError, TypeError, OverflowError):
            return None
        return contract_key(proof)
    return None


def _load_index(path: Path) -> dict:
    if not path.is_file():
        return {"schema": SCHEMA, "last_run": "", "seen": {}}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("V4_DISCOVERY_INDEX_INVALID") from exc
    if (not isinstance(obj, dict) or obj.get("schema") != SCHEMA or
            not isinstance(obj.get("last_run"), str) or
            not isinstance(obj.get("seen"), dict) or
            not all(isinstance(k, str) and isinstance(v, str)
                    for k, v in obj["seen"].items())):
        raise RuntimeError("V4_DISCOVERY_INDEX_INVALID")
    return obj


def first_seen(root: Path, current_run: str) -> dict[str, str]:
    """Incrementally replay saved run proofs, then persist earliest timestamps.

    The first invocation backfills existing completed runs; later invocations
    read only newer runs. A failure never overwrites original market evidence.
    Two mail channels share this same per-run ordering/first-seen timestamp.
    """
    root = Path(root)
    path = root / INDEX
    record = _load_index(path)
    seen = record["seen"]
    last_run = record["last_run"]
    folders = sorted((root / "runs").iterdir())
    changed = False
    for folder in folders:
        if not folder.is_dir() or not (last_run < folder.name <= current_run):
            continue
        moment = _run_time(folder.name)
        if moment is None:
            continue
        manifest = folder / "manifest.json"
        proofs = folder / "all_proofs.jsonl"
        if not manifest.is_file() or not proofs.is_file():
            continue
        try:
            status = json.loads(manifest.read_text(encoding="utf-8")).get("status")
        except (OSError, ValueError):
            continue
        if status != "SHADOW_RECORDED":
            continue
        with proofs.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                proof = json.loads(line)
                # Skip non-market/non-contract rows before deeper inspection.
                if proof.get("kind") not in ("market", "contract", "blueprint_manufacturing"):
                    continue
                key = _discovered_key(proof)
                if key is not None and key not in seen:
                    seen[key] = moment
                    changed = True
        last_run = folder.name
        changed = True
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".json.part")
        try:
            temp.write_text(json.dumps({"schema": SCHEMA, "last_run": last_run,
                                        "seen": seen}, ensure_ascii=False,
                                       separators=(",", ":"), sort_keys=True),
                            encoding="utf-8")
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
    return seen


def order_by_discovery(leads: list[dict], *, kind: str, seen: dict[str, str],
                       fallback_run: str) -> list[dict]:
    """Newly discovered candidates before old, with net profit as tie-breaker."""
    key_fn = (market_key if kind == "market" else
              blueprint_key if kind == "blueprint" else contract_key)
    fallback = _run_time(fallback_run) or "1970-01-01T00:00:00Z"
    enriched = []
    for lead in leads:
        copy = dict(lead)
        copy["first_seen_at"] = seen.get(key_fn(lead), fallback)
        enriched.append(copy)
    return sorted(enriched, key=lambda x: (
        x["first_seen_at"], _number(x.get("net_profit_snapshot")) or 0,
        _number(x.get("roi_snapshot")) or 0,
    ), reverse=True)
