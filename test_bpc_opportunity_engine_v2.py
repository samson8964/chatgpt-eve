import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import bpc_opportunity_engine_v2 as bpc
import export_bpc_v2_safe as safe_export
import build_bpc_v2_safe_mail_preview as preview


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
        self.assertAlmostEqual(h["fill_days"], 1.0)
        self.assertEqual(h["liquidity_label"], "high")

    def test_safe_export_only_keeps_strict_safe_rows(self):
        rows = [
            {"contract_id": 1, "v2_status": "SAFE", "v2_live_net_profit": 50_000_000, "v2_live_net_roi": 0.20, "v2_stress_net_profit": 20_000_000, "v2_orderbook_complete": True, "v2_score": 90},
            {"contract_id": 2, "v2_status": "CHANGED", "v2_live_net_profit": 80_000_000, "v2_live_net_roi": 0.30, "v2_stress_net_profit": 10_000_000, "v2_orderbook_complete": True, "v2_score": 80},
            {"contract_id": 3, "v2_status": "SAFE", "v2_live_net_profit": 10_000_000, "v2_live_net_roi": 0.20, "v2_stress_net_profit": 8_000_000, "v2_orderbook_complete": True, "v2_score": 70},
            {"contract_id": 4, "v2_status": "SAFE", "v2_live_net_profit": 60_000_000, "v2_live_net_roi": 0.15, "v2_stress_net_profit": -1, "v2_orderbook_complete": True, "v2_score": 60},
        ]
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "in.csv"
            out = Path(td) / "out.csv"
            pd.DataFrame(rows).to_csv(source, index=False)
            with patch.object(safe_export, "SOURCE", source), patch.object(safe_export, "OUT", out):
                safe_export.main()
            got = pd.read_csv(out)
        self.assertEqual(list(got["contract_id"]), [1])

    def test_safe_mail_preview_excludes_non_safe_rows(self):
        rows = [
            {"contract_id": 11, "products": "5x Test Module II", "v2_status": "SAFE", "v2_grade": "A", "v2_score": 80, "v2_live_net_profit": 60_000_000, "v2_live_net_roi": 0.20, "v2_stress_net_profit": 30_000_000, "v2_orderbook_complete": True, "v2_est_fill_days": 1.5, "v2_product_vwap": 20_000_000, "v2_product_slippage": 0.01, "v2_material_max_slippage": 0.02},
            {"contract_id": 12, "products": "5x Fragile Module II", "v2_status": "CHANGED", "v2_grade": "C", "v2_score": 50, "v2_live_net_profit": 100_000_000, "v2_live_net_roi": 0.30, "v2_stress_net_profit": -5_000_000, "v2_orderbook_complete": True, "v2_est_fill_days": 1.0, "v2_product_vwap": 30_000_000, "v2_product_slippage": 0.08, "v2_material_max_slippage": 0.01},
        ]
        body = preview.render(pd.DataFrame(rows))
        self.assertIn('Test Module II', body)
        self.assertNotIn('Fragile Module II', body)
        self.assertIn('contract:0//11', body)


if __name__ == "__main__":
    unittest.main()
