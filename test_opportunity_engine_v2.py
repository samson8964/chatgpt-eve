import tempfile
import unittest
from pathlib import Path

from candidate_pool import record_candidate_pool, select_candidate_pool

from opportunity_engine_v2 import (
    analyze_contract_items,
    classify_execution_status,
    cross_book_arbitrage,
    drop_best_price_level,
    liquidate_bundle,
    meets_profit_density,
    opportunity_score,
    profit_density,
    walk_book,
)


class OpportunityEngineV2Tests(unittest.TestCase):
    def test_walk_book_vwap_and_slippage(self):
        book = [
            {"price": 100.0, "vol": 2, "min": 1},
            {"price": 90.0, "vol": 3, "min": 1},
        ]
        fill = walk_book(book, 4)
        self.assertTrue(fill.complete)
        self.assertEqual(fill.filled, 4)
        self.assertAlmostEqual(fill.value, 380.0)
        self.assertAlmostEqual(fill.avg_price, 95.0)
        self.assertAlmostEqual(fill.slippage_pct, 0.05)

    def test_stress_removes_entire_best_level(self):
        book = [
            {"price": 100.0, "vol": 2, "min": 1},
            {"price": 100.0, "vol": 5, "min": 1},
            {"price": 90.0, "vol": 3, "min": 1},
        ]
        stressed = drop_best_price_level(book)
        self.assertEqual(len(stressed), 1)
        self.assertEqual(stressed[0]["price"], 90.0)

    def test_bundle_requires_full_depth(self):
        books = {
            1: [{"price": 10.0, "vol": 3, "min": 1}],
            2: [{"price": 20.0, "vol": 1, "min": 1}],
        }
        quote = liquidate_bundle({1: 3, 2: 2}, books, 0.0)
        self.assertFalse(quote["complete"])
        self.assertAlmostEqual(quote["coverage"], 4 / 5)

    def test_cross_book_uses_depth_and_tax(self):
        asks = [
            {"price": 80.0, "vol": 2, "min": 1},
            {"price": 90.0, "vol": 2, "min": 1},
        ]
        bids = [
            {"price": 120.0, "vol": 1, "min": 1},
            {"price": 110.0, "vol": 3, "min": 1},
        ]
        q = cross_book_arbitrage(asks, bids, sales_tax_rate=0.10, min_marginal_roi=0.05)
        self.assertIsNotNone(q)
        self.assertEqual(q["quantity"], 4)
        self.assertGreater(q["net_profit"], 0)
        self.assertLess(q["destination_worst"], q["destination_best"])

    def test_fitted_rig_exclusion_and_capital_block(self):
        type_objs = {
            100: {"name": "Naglfar", "group_id": 485},
            200: {"name": "Large Core Defense Field Extender II", "group_id": 999},
            300: {"name": "Siege Module II", "group_id": 998},
        }
        group_objs = {
            485: {"name": "Dreadnought", "category_id": 6},
            999: {"name": "Shield Rigs", "category_id": 7},
            998: {"name": "Siege Module", "category_id": 7},
        }
        rows = [
            {"type_id": 100, "quantity": 1, "is_singleton": True},
            {"type_id": 200, "quantity": 2, "is_singleton": True},
            {"type_id": 300, "quantity": 1, "is_singleton": True},
        ]
        f = analyze_contract_items(rows, type_objs, group_objs)
        self.assertTrue(f.has_ship)
        self.assertTrue(f.has_highsec_restricted_ship)
        self.assertNotIn(200, f.adjusted_itemq)
        self.assertNotIn(300, f.adjusted_itemq)
        self.assertIn(300, f.excluded_market_singletons)

    def test_execution_status(self):
        self.assertEqual(classify_execution_status(True, 100, 0.2, 50, 0.02), "SAFE")
        self.assertEqual(classify_execution_status(True, 100, 0.2, -1, 0.02), "CHANGED")
        self.assertEqual(classify_execution_status(False, 100, 0.2, 50, 0.02), "DANGER")
        self.assertEqual(classify_execution_status(True, 100, 0.2, 50, 0.02, ["blocked"]), "DANGER")

    def test_score_penalizes_changed(self):
        safe = opportunity_score(50_000_000, 0.2, 50_000, 80, 40_000_000, 1, 1.0, 0.02, "SAFE")
        changed = opportunity_score(50_000_000, 0.2, 50_000, 80, 40_000_000, 1, 1.0, 0.02, "CHANGED")
        self.assertGreater(safe, changed)

    def test_profit_density_hard_gate(self):
        self.assertAlmostEqual(profit_density(30_000_000, 10_000), 3_000)
        self.assertTrue(meets_profit_density(30_000_000, 10_000, 2_000))
        self.assertFalse(meets_profit_density(30_000_000, 20_000, 2_000))
        self.assertTrue(meets_profit_density(1_000_000, 0, 2_000))
        self.assertFalse(meets_profit_density(-1, 0, 2_000))

    def test_candidate_pool_preserves_explore_newest_and_diversity(self):
        rows=[{
            "contract_id":i,
            "snapshot_profit":1_000_000-i*1000,
            "snapshot_roi":i/1000,
            "date_issued":f"2026-09-{1+(i%28):02d}T00:00:00Z",
            "product_type_id":i%20,
        } for i in range(1,101)]
        with tempfile.TemporaryDirectory() as d:
            state=Path(d)/"pool.json"
            record_candidate_pool(state,"x",rows[:40],at="2026-09-29T00:00:00Z")
            selected,stats=select_candidate_pool(
                rows,20,
                metric_shares=(("snapshot_profit",0.40),("snapshot_roi",0.20)),
                newest_share=0.15,exploration_share=0.15,diversity_share=0.10,
                product_key="product_type_id",fill_metrics=("snapshot_profit","snapshot_roi"),
                state_path=state,channel="x",rotation_token="round-a",
            )
            self.assertEqual(len(selected),20)
            reasons={r["selection_reason"] for r in selected}
            self.assertIn("newest",reasons)
            self.assertIn("exploration",reasons)
            self.assertIn("product-diversity",reasons)
            self.assertGreater(stats["never_recent_selected"],0)

    def test_candidate_pool_deterministic_within_round(self):
        rows=[{"contract_id":i,"snapshot_profit":1000-i,"snapshot_roi":i/100,"date_issued":str(i)} for i in range(1,61)]
        a,_=select_candidate_pool(rows,20,metric_shares=(("snapshot_profit",0.40),("snapshot_roi",0.20)),newest_share=0.20,exploration_share=0.20,rotation_token="same")
        b,_=select_candidate_pool(rows,20,metric_shares=(("snapshot_profit",0.40),("snapshot_roi",0.20)),newest_share=0.20,exploration_share=0.20,rotation_token="same")
        self.assertEqual([x["contract_id"] for x in a],[x["contract_id"] for x in b])


if __name__ == "__main__":
    unittest.main()
