"""Verified public NPC sell books and unchanged V4 matched-depth evaluator.

Formal opportunity source: Amarr VIII and Dodixie IX, from COMPLETE official
ESI region books for Domain and Sinq Laison. Jita BUY orders are captured
together with them. No snapshot or EVE Ref estimate can directly pass as a
verified fresh public source. No orders, credentials or local tasks are changed.
"""
from __future__ import annotations

import gzip
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from v4.catalog import Catalog
from v4.engine import Order, market_proof
from v4.esi_private_source_jita_ab import JITA, POLICY, ParityError
from v4.esi_same_engine_market_shadow import VALIDATED_RUN, _sort_books
from v4.market_execution import gross_depth_upper_bound

FORGE = 10000002
NPC_REGIONS = {
    10000032: ("Dodixie", 60011866),  # Sinq Laison
    10000043: ("Amarr", 60008494),    # Domain
}
REGIONS = tuple(sorted((FORGE, *NPC_REGIONS)))


def _stamp(value):
    try:
        stamp = parsedate_to_datetime(str(value))
        if stamp.tzinfo is None:
            raise ValueError("naive ESI time")
        return stamp.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        raise ParityError("NPC_ESI_INVALID_LAST_MODIFIED") from None


def fresh_public_books(root, report, *, now=None, max_age_minutes=15):
    """Return (Jita BUY book, NPC SELL books, Jita evidence, per-NPC evidence).

    The report and each region archive must agree on all rows; rejects stale,
    partial, mixed-version, missing-field, or duplicate official ESI inputs.
    """
    if not isinstance(report, dict) or not VALIDATED_RUN.fullmatch(str(report.get("run", ""))):
        raise ParityError("NPC_ESI_INVALID_RUN")
    run_id = report["run"]
    folder = Path(root) / "esi-parallel-validation" / run_id
    path = folder / "report.json"
    if not path.is_file():
        raise ParityError("NPC_ESI_REPORT_NOT_FOUND")
    saved = json.loads(path.read_text(encoding="utf-8"))
    if (saved.get("run") != run_id
            or saved.get("status") != "PARTIAL_REGION_TEST_ONLY"
            or saved.get("requested_region_ids") != list(REGIONS)
            or saved.get("attempted_regions") != len(REGIONS)
            or saved.get("full_universe_requested") is not False
            or saved.get("failed_regions") or saved.get("unverified_404_regions")
            or len(saved.get("regions") or []) != len(REGIONS)
            or (report.get("run") != saved.get("run"))
            or (report.get("requested_region_ids") != saved.get("requested_region_ids"))
            or (report.get("status") != saved.get("status"))):
        raise ParityError("NPC_ESI_INCOMPLETE_REGIONAL_COVERAGE")
    fields = {"order_id", "region_id", "location_id", "type_id",
              "is_buy_order", "price", "volume_remain", "min_volume",
              "range", "volume_total"}
    if not fields.issubset(saved.get("archive_execution_fields") or []):
        raise ParityError("NPC_ESI_ARCHIVE_FIELDS_INCOMPLETE")
    region_info = {x.get("region_id"): x for x in saved["regions"]}
    if set(region_info) != set(REGIONS):
        raise ParityError("NPC_ESI_REGION_IDS_MISMATCH")
    if int(saved.get("esi_unique_orders", -1)) != sum(
            int(region_info[r].get("orders", -1)) for r in REGIONS):
        raise ParityError("NPC_ESI_TOTAL_ROW_COUNT_MISMATCH")

    reference_time = now or datetime.now(timezone.utc)
    if reference_time.tzinfo is None:
        raise ParityError("NPC_ESI_COMPARISON_CLOCK_NAIVE")
    jita, npc = defaultdict(list), defaultdict(list)
    evidence = {}
    seen = set()
    for region_id in REGIONS:
        region = region_info[region_id]
        if (region.get("status") != "COMPLETE"
                or int(region.get("pages") or 0) < 1
                or int(region.get("orders") or 0) <= 0):
            raise ParityError("NPC_ESI_REGION_NOT_COMPLETE")
        stamp = _stamp(region.get("last_modified"))
        age = (reference_time - stamp).total_seconds() / 60
        if not (0 <= age <= max_age_minutes):
            raise ParityError("NPC_ESI_REGION_SNAPSHOT_STALE")
        archive = folder / "regions" / f"{region_id}.jsonl.gz"
        if not archive.is_file():
            raise ParityError("NPC_ESI_REGION_ARCHIVE_MISSING")
        rows, matched = 0, 0
        with gzip.open(archive, "rt", encoding="utf-8") as stream:
            for line in stream:
                try:
                    raw = json.loads(line)
                    if not isinstance(raw, dict) or not fields.issubset(raw):
                        raise ValueError("missing order fields")
                    if int(raw["region_id"]) != region_id:
                        raise ValueError("wrong order region")
                    oid = int(raw["order_id"])
                    if oid <= 0 or oid in seen:
                        raise ValueError("duplicate or invalid order ID")
                    seen.add(oid)
                    rows += 1
                    lid = int(raw["location_id"])
                    if (region_id == FORGE and lid == JITA and
                            str(raw["is_buy_order"]).lower() in ("1", "true")):
                        order = Order.parse(raw)
                        if not order.buy:
                            raise ValueError("wrong Jita side")
                        jita[(JITA, order.type_id, True)].append(order)
                        matched += 1
                    elif region_id in NPC_REGIONS and lid == NPC_REGIONS[region_id][1]:
                        order = Order.parse(raw)
                        if not order.buy:
                            npc[(lid, order.type_id, False)].append(order)
                            matched += 1
                except (ValueError, TypeError, KeyError, OverflowError, json.JSONDecodeError):
                    raise ParityError("NPC_ESI_ARCHIVE_ORDER_INVALID") from None
        if rows != int(region["orders"]):
            raise ParityError("NPC_ESI_REGION_ARCHIVE_COUNT_MISMATCH")
        label = "Jita" if region_id == FORGE else NPC_REGIONS[region_id][0]
        evidence[label] = {
            "region_id": region_id,
            "station_id": JITA if region_id == FORGE else NPC_REGIONS[region_id][1],
            "status": "COMPLETE",
            "active_region_orders": rows,
            "selected_station_orders": matched,
            "pages": int(region["pages"]),
            "last_modified": stamp.isoformat(),
            "snapshot_age_minutes": round(age, 2),
        }
    if not jita:
        raise ParityError("NPC_ESI_NO_JITA_BUY_ORDERS")
    _sort_books(jita)
    _sort_books(npc)
    jita_info = {
        "archive_run": run_id,
        "region_id": FORGE,
        "verified_pages": evidence["Jita"]["pages"],
        "forge_active_orders": evidence["Jita"]["active_region_orders"],
        "jita_buy_orders": evidence["Jita"]["selected_station_orders"],
        "last_modified": evidence["Jita"]["last_modified"],
        "age_at_private_comparison_minutes": evidence["Jita"]["snapshot_age_minutes"],
        "max_allowed_age_minutes": max_age_minutes,
        "archive_reused_read_only": True,
    }
    return dict(jita), dict(npc), jita_info, {
        label: value for label, value in evidence.items() if label != "Jita"
    }


def evaluate_npc(asks, jita, catalog: Catalog, haul_fn):
    """Same profit/stress/VWAP policy as structures, different verified sources."""
    labels = {station_id: name for name, station_id in NPC_REGIONS.values()}
    counters, by_station, proofs = Counter(), defaultdict(Counter), {}
    for (location, typ, buy), orders in sorted(asks.items()):
        if buy or location not in labels:
            raise ParityError("NPC_SELL_SCOPE_MISMATCH")
        label = labels[location]
        by_station[label]["sell_types"] += 1
        bids = jita.get((JITA, typ, True), ())
        if not bids:
            by_station[label]["NO_JITA_BUY"] += 1
            counters["NO_JITA_BUY"] += 1
            continue
        if orders[0].price >= bids[0].price:
            by_station[label]["NOT_PRICE_CROSSED"] += 1
            counters["NOT_PRICE_CROSSED"] += 1
            continue
        if gross_depth_upper_bound(orders, bids) < POLICY.profit_floor:
            by_station[label]["BELOW_GROSS_DEPTH_CEILING"] += 1
            counters["BELOW_GROSS_DEPTH_CEILING"] += 1
            continue
        by_station[label]["PREFILTER_PASSED"] += 1
        counters["PREFILTER_PASSED"] += 1
        volume = catalog.volume(typ)
        haul_for_units = lambda units, src=location, v=volume: (
            haul_fn(src, JITA, float(units) * v) if v is not None else None
        )
        result = market_proof(
            orders, bids, source_location=location,
            destination_location=JITA, type_id=typ, volume_m3=volume,
            haul_isk=None, haul_for_units=haul_for_units,
            policy=POLICY, allowed=True, fresh=True,
        )
        passed = result.get("status") == "MAIL"
        counters["MODEL_PASS_RESEARCH_ONLY" if passed else
                 "REJECT_" + str(result.get("reason", "UNKNOWN"))] += 1
        by_station[label]["MODEL_PASS_RESEARCH_ONLY" if passed else "REJECTED"] += 1
        proofs[f"{label}:{typ}"] = {
            "station": label, "station_id": location, "type_id": typ,
            "hypothetical_model_pass": passed,
            "reason": result.get("reason"), "quantity": result.get("quantity"),
            "net_profit_isk": result.get("profit"), "roi": result.get("roi"),
            "stress_profit_isk": result.get("stress_profit"),
            "haul_isk": result.get("haul"),
            "source_vwap_isk": result.get("source_vwap_isk_per_unit"),
            "jita_buy_vwap_isk": result.get("jita_vwap_isk_per_unit"),
        }
    for name in labels.values():
        by_station[name].setdefault("sell_types", 0)
    counters["evaluated_npc_sell_type_pairs"] = len(asks)
    return proofs, dict(counters), {name: dict(v) for name, v in by_station.items()}
