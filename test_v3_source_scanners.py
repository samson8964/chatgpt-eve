import unittest

from v3_source_market_scanner import haul_cost, match_books, select_candidate_ids, select_trade_quote
from v3_engine import PolicyConfig
from v3_structure_contract_scanner import choose_candidate_ids


class V3SourceScannerTests(unittest.TestCase):
    def test_source_market_matches_only_profitable_depth(self):
        asks = [
            {"price": 100.0, "vol": 5, "min": 1},
            {"price": 120.0, "vol": 5, "min": 1},
        ]
        bids = [
            {"price": 150.0, "vol": 4, "min": 1},
            {"price": 110.0, "vol": 20, "min": 1},
        ]
        q = match_books(asks, bids, min_marginal_roi=0.10)
        self.assertIsNotNone(q)
        self.assertEqual(q["quantity"], 4)
        self.assertAlmostEqual(q["source_cost"], 400.0)
        self.assertAlmostEqual(q["destination_gross"], 600.0)

    def test_optimize_small_high_roi_fill_instead_of_diluting_with_tail(self):
        asks = [
            {"price": 100.0, "vol": 1_000_000, "min": 1},
            {"price": 105.0, "vol": 1_000_000, "min": 1},
            {"price": 130.0, "vol": 20_000_000, "min": 1},
        ]
        bids = [
            {"price": 200.0, "vol": 1_000_000, "min": 1},
            {"price": 180.0, "vol": 1_000_000, "min": 1},
            {"price": 140.0, "vol": 20_000_000, "min": 1},
        ]
        full = match_books(asks, bids, min_marginal_roi=0)
        self.assertLess(full["net_roi_before_haul"], 0.10)
        selected, cutoff = select_trade_quote(
            asks, bids, unit_m3=0.001, jumps=0, cfg=PolicyConfig()
        )
        self.assertGreaterEqual(cutoff, 0.10)
        self.assertEqual(selected["quantity"], 2_000_000)
        self.assertGreater(selected["net_before_haul"] - haul_cost(2_000, 0), 50_000_000)

    def test_haul_cost_supports_base_per_m3_and_jump(self):
        self.assertGreaterEqual(haul_cost(100.0, 10), 2_000_000.0)

    def test_candidate_pool_keeps_profit_and_roi_buckets(self):
        rows = [
            {"type_id": 1, "net_before_haul": 100, "net_roi_before_haul": 0.1},
            {"type_id": 2, "net_before_haul": 90, "net_roi_before_haul": 0.9},
            {"type_id": 3, "net_before_haul": 80, "net_roi_before_haul": 0.2},
        ]
        ids = select_candidate_ids(rows, 2)
        self.assertIn(1, ids)
        self.assertIn(2, ids)

    def test_structure_contract_pool_includes_newest_bucket(self):
        rows = [
            {"contract_id": 1, "snapshot_profit": 100, "snapshot_roi": 0.2, "date_issued": "2026-10-01"},
            {"contract_id": 2, "snapshot_profit": 90, "snapshot_roi": 0.9, "date_issued": "2026-10-02"},
            {"contract_id": 3, "snapshot_profit": 1, "snapshot_roi": 0.01, "date_issued": "2026-10-07"},
        ]
        ids = choose_candidate_ids(rows, 3)
        self.assertEqual(set(ids), {1, 2, 3})


if __name__ == "__main__":
    unittest.main()
