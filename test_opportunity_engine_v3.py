import math
import unittest

from opportunity_engine_v3 import cash_floor_bundle, conservative_sell_bundle, procure_bundle, select_candidate_union


class OpportunityEngineV3Tests(unittest.TestCase):
    def test_cash_floor_values_only_executable_units(self):
        books = {
            1: [{"price": 100.0, "vol": 3, "min": 1}],
            2: [],
        }
        q = cash_floor_bundle({1: 5, 2: 2}, books, 0.10)
        self.assertEqual(q["filled_units"], 3)
        self.assertEqual(q["requested_units"], 7)
        self.assertAlmostEqual(q["gross"], 300.0)
        self.assertAlmostEqual(q["net_after_tax"], 270.0)
        self.assertAlmostEqual(q["coverage"], 3 / 7)
        self.assertTrue(q["has_executable_value"])

    def test_procurement_requires_every_requested_unit(self):
        books = {1: [{"price": 10.0, "vol": 4, "min": 1}]}
        bad = procure_bundle({1: 5}, books)
        self.assertFalse(bad["complete"])
        good = procure_bundle({1: 4}, books)
        self.assertTrue(good["complete"])
        self.assertEqual(good["cost"], 40.0)

    def test_candidate_union_keeps_recent_and_roi_candidates(self):
        rows = []
        for i in range(10):
            rows.append({
                "contract_id": i + 1,
                "snapshot_profit": 1000 - i * 50,
                "snapshot_roi": 0.10 + i * 0.01,
                "date_issued": f"2026-09-{i+1:02d}T00:00:00Z",
            })
        rows.append({"contract_id": 999, "snapshot_profit": -1, "snapshot_roi": -1, "date_issued": "2099-01-01T00:00:00Z"})
        picked = select_candidate_union(rows, 6, profit_quota=2, roi_quota=2, recent_quota=2)
        ids = {x["contract_id"] for x in picked}
        self.assertIn(1, ids)
        self.assertIn(10, ids)
        self.assertIn(999, ids)
        self.assertLessEqual(len(ids), 6)

    def test_conservative_sell_uses_lower_price_anchor_and_haircut(self):
        sells = {1: [{"price": 120.0, "vol": 100, "min": 1}]}
        history = {1: {"days": 30, "vwap_7d": 110.0, "vwap_30d": 100.0, "avg_daily_volume_7d": 50.0, "avg_daily_volume_30d": 40.0}}
        q = conservative_sell_bundle({1: 10}, sells, history, participation=0.20, price_haircut=0.97)
        self.assertTrue(q["complete"])
        self.assertAlmostEqual(q["gross"], 100.0 * 0.97 * 10)
        self.assertAlmostEqual(q["fill_days"], 1.0)
        self.assertLess(q["stress_gross"], q["gross"])

    def test_conservative_sell_fails_closed_without_history(self):
        sells = {1: [{"price": 120.0, "vol": 100, "min": 1}]}
        q = conservative_sell_bundle({1: 10}, sells, {}, participation=0.20, price_haircut=0.97)
        self.assertFalse(q["complete"])
        self.assertEqual(q["gross"], 0.0)
        self.assertEqual(q["fill_days"], 0.0)


if __name__ == "__main__":
    unittest.main()
