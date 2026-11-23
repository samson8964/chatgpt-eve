"""No-network source audit fixtures for global PLEX and contract filter attrition."""
import unittest
from datetime import datetime, timezone

import pandas as pd

from v4.celebration_crate_source_audit import analyze, GLOBAL_PLEX_REGION
from v4.celebration_crate_radar import JITA, PLEX

CJ = 1049588174021
OFF = 60006789


class CelebrationCrateSourceAuditTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 23, 3, 10, tzinfo=timezone.utc)
        self.market = pd.DataFrame([
            {"type_id": PLEX, "region_id": GLOBAL_PLEX_REGION,
             "location_id": OFF, "price": 4_900_000, "volume_remain": 5000,
             "order_id": 1, "is_buy_order": True},
            {"type_id": PLEX, "region_id": 10000002,
             "location_id": JITA, "price": 4_700_000, "volume_remain": 100,
             "order_id": 2, "is_buy_order": True},
            {"type_id": 80240, "region_id": 10000002,
             "location_id": JITA, "price": 92_000_000, "volume_remain": 1,
             "order_id": 3, "is_buy_order": False},
            {"type_id": 80240, "region_id": 10000002,
             "location_id": OFF, "price": 1_000, "volume_remain": 1,
             "order_id": 4, "is_buy_order": False},
        ])
        self.contracts = pd.DataFrame([
            {"contract_id": 11, "start_location_id": CJ, "price": 90_000_000,
             "type": "item_exchange", "status": "outstanding",
             "date_expired": "2026-12-01T00:00:00Z"},
            {"contract_id": 12, "start_location_id": CJ, "price": 10_000_000,
             "type": "item_exchange", "status": "outstanding",
             "date_expired": "2026-12-01T00:00:00Z"},
            {"contract_id": 13, "start_location_id": CJ, "price": 10_000_000,
             "type": "item_exchange", "status": "finished",
             "date_expired": "2026-12-01T00:00:00Z"},
        ])
        self.items = pd.DataFrame([
            {"contract_id": 11, "type_id": 80240, "quantity": 1, "is_included": True},
            {"contract_id": 12, "type_id": 80240, "quantity": 1, "is_included": True},
            {"contract_id": 12, "type_id": 34, "quantity": 1, "is_included": False},
            {"contract_id": 13, "type_id": 80240, "quantity": 1, "is_included": True},
        ])

    def test_global_bid_has_more_coverage_than_jita(self):
        report = analyze(self.market, self.contracts, self.items,
                         structure_ids={CJ}, at=self.now)
        plex = report["plex"]
        self.assertEqual(plex["global_market_bids"]["orders"], 1)
        self.assertEqual(plex["global_market_bids"]["units"], 5000)
        self.assertEqual(plex["global_market_bids"]["best_bid_isk"], 4_900_000)
        self.assertEqual(plex["jita_location_bids"]["best_bid_isk"], 4_700_000)
        self.assertEqual(plex["interpretation"],
                         "GLOBAL_REGION_PRESENT_JITA_ONLY_BASIS_MAY_UNDERVALUE")
        box = report["listed_boxes"]["80240"]
        self.assertEqual(box["all_public_market_sell_orders"], 2)
        self.assertEqual(box["in_scope_public_market_sell_orders"], 1)
        self.assertGreater(box["optimistic_one_box_before_haul_global_isk"],
                           box["optimistic_one_box_before_haul_jita_isk"])

    def test_contract_failure_funnel(self):
        report = analyze(self.market, self.contracts, self.items,
                         structure_ids={CJ}, at=self.now)
        stats = report["contracts"]
        self.assertEqual(stats["crate_included_contract_ids_in_scope"], 3)
        self.assertEqual(stats["excluded_by_requested_items_in_scope"], 1)
        self.assertEqual(stats["non_outstanding_in_scope"], 1)
        self.assertEqual(stats["potentially_eligible_before_plex_and_freight"], 1)

    def test_empty_global_market_is_not_silent_price_zero(self):
        market = self.market[self.market["region_id"] != GLOBAL_PLEX_REGION]
        report = analyze(market, self.contracts, self.items,
                         structure_ids={CJ}, at=self.now)
        self.assertEqual(report["plex"]["global_market_bids"]["orders"], 0)
        self.assertEqual(report["plex"]["interpretation"],
                         "GLOBAL_REGION_NOT_IN_SNAPSHOT_VERIFY_ESI_19000001")

    def test_missing_region_column_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "REGION_OR_FIELDS_MISSING"):
            analyze(self.market.drop(columns=["region_id"]),
                    self.contracts, self.items, at=self.now)


if __name__ == "__main__":
    unittest.main()
