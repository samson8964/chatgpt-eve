"""Offline, no-network regression tests for staged 74L2-U market enrollment."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v4 import structure_registry as registry
from v4.candidate_station_full_probe import probe as full_probe
from v4.esi_private_source_jita_ab import (
    ParityError, _private_asks, _evaluate, STRUCTURES as APPROVED_STATIONS,
    AUTHORIZED_LANES, LANE_TO_LABEL,
)
from v4.local_service import execute
from v4.engine import Order

BANESTAR = 1050474463169
KEY = "K" * 48


def order(ident, location, side=False, price=1e6, typ=34):
    return {
        "order_id": ident, "location_id": location,
        "is_buy_order": side, "type_id": typ,
        "price": price, "volume_remain": 20, "min_volume": 1,
        "range": "station",
    }


def full_fetch(url, params, headers, timeout):
    assert params["auth_profile"] == "banestar"
    assert params["structure_id"] == BANESTAR
    assert headers["Authorization"] == "Bearer " + KEY
    page = params["page"]
    return {
        "ok": True,
        "structure_id": BANESTAR,
        "page": page,
        "pages": 2,
        "orders": [order(100 + page, BANESTAR, page == 2)],
    }, {}


class Catalog:
    def volume(self, typ):
        return 1


class BanestarEnrollmentTests(unittest.TestCase):
    def test_only_exact_user_opt_in_activates_registry(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "banestar.enabled"
            with patch.object(registry, "ENABLE_FILE", p):
                self.assertFalse(registry.banestar_enabled())
                p.write_text("yes", encoding="utf8")
                self.assertFalse(registry.banestar_enabled())
                p.write_text(registry.ENABLE_CONTENT, encoding="utf8")
                self.assertTrue(registry.banestar_enabled())
            self.assertEqual(len(registry.BASE_LANES), 3)
            self.assertEqual(registry.BANESTAR_LANE[2], BANESTAR)
            self.assertEqual(registry.BANESTAR_LANE[3], "banestar")

    def test_full_page_canary_aggregates_only_and_never_enrolls(self):
        result = full_probe(key=KEY, fetch=full_fetch,
                            sleep=lambda _: None, jitter=lambda: 0)
        self.assertEqual(result["status"], "FULL_BOOK_VALIDATED_NOT_ENROLLED")
        self.assertEqual(result["market_health"]["pages"], 2)
        self.assertEqual(result["market_health"]["pages_fetched"], 2)
        self.assertEqual(result["active_buy_orders"], 1)
        self.assertEqual(result["active_sell_orders"], 1)
        self.assertEqual(result["distinct_sell_type_ids"], 1)
        self.assertFalse(result["enrolled"])
        self.assertFalse(result["orders_saved"])
        self.assertNotIn(KEY, str(result))

    def test_full_page_canary_failure_does_not_report_success(self):
        def fail_second(url, params, headers, timeout):
            response, h = full_fetch(url, params, headers, timeout)
            if params["page"] == 2:
                response["pages"] = 4
            return response, h
        result = full_probe(key=KEY, fetch=fail_second,
                            sleep=lambda _: None, jitter=lambda: 0)
        self.assertEqual(result["status"], "FULL_BOOK_COLLECTION_FAILED")
        self.assertEqual(result["market_health"]["reason"],
                         "PAGINATION_DRIFT_OR_INVALID")

    def test_full_book_rejects_duplicate_ids(self):
        def duplicate(url, params, headers, timeout):
            response, h = full_fetch(url, params, headers, timeout)
            response["orders"][0]["order_id"] = 100
            return response, h
        result = full_probe(key=KEY, fetch=duplicate,
                            sleep=lambda _: None, jitter=lambda: 0)
        self.assertEqual(result["status"], "FULL_BOOK_ROW_INTEGRITY_FAILED")

    def test_active_scope_is_consistent_across_modules(self):
        from v4.deep_scan import STRUCTURES as DEEP
        from v4.market_depth import STATIONS
        from v4.market_station_audit import LABEL_TO_LANE
        from v4.unified_review import LOCATION_NAMES
        self.assertEqual(DEEP, registry.STRUCTURES)
        self.assertEqual(STATIONS, registry.STATIONS)
        self.assertEqual(APPROVED_STATIONS, STATIONS)
        self.assertEqual(AUTHORIZED_LANES, DEEP)
        self.assertEqual(set(LANE_TO_LABEL), set(DEEP))
        self.assertEqual(set(LABEL_TO_LANE), set(STATIONS))
        for name, loc in STATIONS.items():
            self.assertEqual(LOCATION_NAMES[loc], name)

    def test_fourth_station_full_coverage_required_and_evaluated(self):
        # Exercise the production valuation engine with a synthetic fourth
        # lane even when the local enrollment flag is deliberately OFF.
        base_lanes = dict(AUTHORIZED_LANES)
        base_stations = dict(APPROVED_STATIONS)
        base_labels = dict(LANE_TO_LABEL)
        base_lanes["banestar"] = (BANESTAR, "banestar")
        base_stations["74L2-U"] = BANESTAR
        base_labels["banestar"] = "74L2-U"
        rows = [order(12345, BANESTAR, False)]
        health = {
            lane: {"status": "COMPLETE", "location": loc,
                   "orders": 1 if lane == "banestar" else 0,
                   "pages": 1, "pages_fetched": 1}
            for lane, (loc, _) in base_lanes.items()
        }
        with patch.dict(AUTHORIZED_LANES, base_lanes, clear=True), \
             patch.dict(APPROVED_STATIONS, base_stations, clear=True), \
             patch.dict(LANE_TO_LABEL, base_labels, clear=True):
            asks, counts, hashes = _private_asks(rows, health)
            self.assertEqual(counts["active_sell_orders"], 1)
            self.assertIn(str(BANESTAR), hashes)
            bids = {(60003760, 34, True): [
                Order.parse(order(80001, 60003760, True, 10e6)),
                Order.parse(order(80002, 60003760, True, 9e6)),
            ]}
            result, _, by_station = _evaluate(
                asks, bids, Catalog(), lambda *_: 10_000_000)
            self.assertIn("74L2-U:34", result)
            self.assertIn("74L2-U", by_station)
            health["banestar"]["status"] = "FAILED"
            with self.assertRaisesRegex(ParityError, "PRIVATE_STRUCTURE_LANE_FAILED"):
                _private_asks(rows, health)

    def test_local_service_missing_fourth_lane_is_never_complete(self):
        def scan(root):
            return {
                "status": "SHADOW_RECORDED", "mail_enabled": False,
                "run_folder": str(root / "runs" / "example"),
                "coverage_gate": "INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
                "source_input_integrity": "ALL_PARSED",
                "structure_health": {
                    "four_h": {"status": "COMPLETE", "pages": 1, "pages_fetched": 1},
                    "cj": {"status": "COMPLETE", "pages": 1, "pages_fetched": 1},
                    "o4t": {"status": "COMPLETE", "pages": 1, "pages_fetched": 1},
                },
            }
        with tempfile.TemporaryDirectory() as td:
            with patch("v4.local_service.storage_check",
                       return_value={"free_gib": 100, "enough_space": True}), \
                 patch("v4.local_service.backup_due", return_value=False), \
                 patch.dict(registry.STRUCTURES,
                            {"banestar": (BANESTAR, "banestar")}):
                status = execute(Path(td), scanner=scan)
        self.assertEqual(status["status"], "DEGRADED_PARTIAL_COVERAGE")
        self.assertEqual(status["structure_status"]["banestar"], "MISSING")


if __name__ == "__main__":
    unittest.main()
