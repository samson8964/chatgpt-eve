import math
import unittest

from opportunity_engine_v3 import (
    conservative_listing_bundle,
    diverse_candidates,
    partial_liquidation,
    procurement_cost,
    v3_status,
)


class OpportunityEngineV3Tests(unittest.TestCase):
    def test_cash_floor_values_partial_depth_and_zeroes_leftovers(self):
        books = {
            1: [
                {"price": 100.0, "vol": 3, "min": 1},
                {"price": 90.0, "vol": 2, "min": 1},
            ]
        }
        q = partial_liquidation({1: 10}, books, 0.05)
        self.assertEqual(q["filled_units"], 5)
        self.assertEqual(q["requested_units"], 10)
        self.assertAlmostEqual(q["gross"], 480.0)
        self.assertAlmostEqual(q["net_after_tax"], 456.0)
        self.assertEqual(q["matched_itemq"], {1: 5})
        self.assertAlmostEqual(q["coverage"], 0.5)

    def test_barter_procurement_requires_full_depth(self):
        books = {1: [{"price": 10.0, "vol": 3, "min": 1}]}
        q = procurement_cost({1: 5}, books)
        self.assertFalse(q["complete"])
        self.assertAlmostEqual(q["cost"], 30.0)

    def test_diverse_pool_keeps_recent_contract_even_if_profit_rank_is_low(self):
        rows = [
            {"contract_id": 1, "snapshot_profit": 100.0, "snapshot_roi": 0.3, "date_issued": "2026-09-01"},
            {"contract_id": 2, "snapshot_profit": 90.0, "snapshot_roi": 0.2, "date_issued": "2026-09-02"},
            {"contract_id": 3, "snapshot_profit": -5.0, "snapshot_roi": -0.1, "date_issued": "2026-09-18"},
        ]
        out = diverse_candidates(rows, total_limit=3, per_metric=1, newest_count=1)
        self.assertEqual({x["contract_id"] for x in out}, {1, 2, 3})

    def test_listing_uses_lowest_reference_and_haircut(self):
        sell = {1: [{"price": 120.0, "vol": 100, "min": 1}]}
        history = {
            1: {
                "vwap_7d": 110.0,
                "vwap_30d": 100.0,
                "avg_daily_volume_7d": 20.0,
                "avg_daily_volume_30d": 10.0,
            }
        }
        q = conservative_listing_bundle({1: 10}, sell, history, haircut=0.05, participation=0.20)
        self.assertTrue(q["complete"])
        self.assertAlmostEqual(q["gross"], 950.0)
        self.assertAlmostEqual(q["estimated_fill_days"], 2.5)

    def test_listing_missing_history_fails_closed(self):
        q = conservative_listing_bundle(
            {1: 1},
            {1: [{"price": 100.0, "vol": 10, "min": 1}]},
            {},
        )
        self.assertFalse(q["complete"])

    def test_status_requires_stress_survival_for_safe(self):
        self.assertEqual(v3_status(50, 0.2, 20, 30, 0.1), "SAFE")
        self.assertEqual(v3_status(50, 0.2, -1, 30, 0.1), "CHANGED")
        self.assertEqual(v3_status(20, 0.2, 20, 30, 0.1), "DANGER")
        self.assertEqual(v3_status(50, 0.2, 20, 30, 0.1, change_pct=0.2), "CHANGED")


if __name__ == "__main__":
    unittest.main()
