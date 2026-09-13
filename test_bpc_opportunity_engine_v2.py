import math
import unittest
from unittest.mock import patch

import bpc_opportunity_engine_v2 as bpc


class BpcOpportunityEngineV2Tests(unittest.TestCase):
    def test_build_job_reconstructs_me_adjusted_materials_and_output(self):
        items = [
            {
                "is_included": True,
                "is_blueprint_copy": True,
                "type_id": 100,
                "runs": 5,
                "quantity": 2,
                "material_efficiency": 10,
                "time_efficiency": 20,
            }
        ]
        fake_bp = {100: {"activities": {"manufacturing": {"materials": {"1": {"type_id": 1, "quantity": 10}}, "products": {"2": {"type_id": 2, "quantity": 1}}}}}}
        with patch.object(bpc, "fetch_many_ref", return_value=fake_bp):
            job, err = bpc.build_job(items)
        self.assertEqual(err, "")
        self.assertIsNotNone(job)
        # 10 units/run * 5 runs * 90% = 45 per copy; two copies => 90.
        self.assertEqual(job["materials"][1], 90)
        self.assertEqual(job["products"][2], 10)

    def test_build_job_rejects_non_bpc_bundle(self):
        items = [{"is_included": True, "is_blueprint_copy": False, "type_id": 100, "runs": 5, "quantity": 1}]
        job, err = bpc.build_job(items)
        self.assertIsNone(job)
        self.assertEqual(err, "non_bpc_item_in_contract")

    def test_quote_bundle_uses_vwap_and_stress_level(self):
        books = {
            7: [
                {"price": 10.0, "vol": 2, "min": 1},
                {"price": 12.0, "vol": 3, "min": 1},
                {"price": 14.0, "vol": 10, "min": 1},
            ]
        }
        q = bpc.quote_bundle({7: 4}, books, "buy_materials")
        self.assertTrue(q["complete"])
        self.assertAlmostEqual(q["value"], 44.0)
        self.assertAlmostEqual(q["rows"][0]["vwap"], 11.0)
        # Stress removes the whole best-price level (10.0), then fills at 12/14.
        self.assertTrue(q["stress_complete"])
        self.assertAlmostEqual(q["stress_value"], 50.0)

    def test_classify_safe_changed_and_danger(self):
        self.assertEqual(bpc.classify(True, 50_000_000, 0.20, 30_000_000, 0.02, 0.01, False), "SAFE")
        self.assertEqual(bpc.classify(True, 50_000_000, 0.20, -1, 0.02, 0.01, False), "CHANGED")
        self.assertEqual(bpc.classify(True, 50_000_000, 0.20, 30_000_000, 0.50, 0.01, False), "CHANGED")
        self.assertEqual(bpc.classify(True, 10_000_000, 0.20, 5_000_000, 0.02, 0.01, False), "DANGER")
        self.assertEqual(bpc.classify(False, 50_000_000, 0.20, 30_000_000, 0.02, 0.01, False), "DANGER")
        self.assertEqual(bpc.classify(True, 50_000_000, 0.20, 30_000_000, 0.02, 0.01, True), "DANGER")

    def test_score_rewards_safe_liquid_opportunity(self):
        safe = bpc.score(100_000_000, 0.25, 100, 80_000_000, 0.01, "SAFE", 1.0)
        changed = bpc.score(100_000_000, 0.25, 100, 80_000_000, 0.01, "CHANGED", 1.0)
        slow = bpc.score(100_000_000, 0.25, 20, 80_000_000, 0.01, "SAFE", 10.0)
        self.assertGreater(safe, changed)
        self.assertGreater(safe, slow)
        self.assertIn(bpc.grade(safe, "SAFE"), {"S", "A", "B", "C"})
        self.assertEqual(bpc.grade(changed, "CHANGED"), "C")

    def test_history_metrics_uses_30_day_participation(self):
        fake = [{"date": f"2026-08-{(i % 28) + 1:02d}", "volume": 100} for i in range(30)]
        with patch.object(bpc, "_get", return_value=(fake, {})):
            h = bpc.history_metrics(123, 35)
        self.assertEqual(h["days"], 30)
        self.assertAlmostEqual(h["avg_daily"], 100.0)
        # participation defaults to 35%, so 35 units is one day of executable flow.
        self.assertAlmostEqual(h["fill_days"], 1.0)
        self.assertEqual(h["liquidity_label"], "high")


if __name__ == "__main__":
    unittest.main()
