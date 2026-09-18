import ast
import unittest
from pathlib import Path

import pandas as pd

import runner
import runner_buy_only
import runner_buy_only_v31
from four_h_market_scanner_v31 import _with_base_haul
from scanner_source import truthy_series


class V31Tests(unittest.TestCase):
    def test_v31_dynamic_scanner_source_compiles(self):
        source = Path("scanner_source.py").read_text(encoding="utf-8")
        source = runner.patch_source(source)
        source = runner_buy_only.apply_policy(source)
        source = runner_buy_only_v31.apply_v31_performance(source)
        ast.parse(source)

    def test_parallel_quote_patch_removes_serial_industry_call(self):
        source = Path("scanner_source.py").read_text(encoding="utf-8")
        source = runner.patch_source(source)
        source = runner_buy_only.apply_policy(source)
        source = runner_buy_only_v31.apply_v31_performance(source)
        self.assertIn("V3.1 parallel industry quote prefetch", source)
        self.assertIn("quote_cache.get", source)
        # The exact-fee loop should read the prefetched cache, not issue its own request.
        marker = source.index('print("6) exact fees")')
        tail = source[marker:]
        self.assertNotIn('q=industry_quote(j["bp_tid"]', tail)

    def test_logistics_base_is_counted_in_market_profit(self):
        q = {
            "haul_cost": 5_000_000.0,
            "net_profit": 100_000_000.0,
            "source_cost": 500_000_000.0,
        }
        out = _with_base_haul(q)
        self.assertGreater(out["haul_cost"], q["haul_cost"])
        self.assertLess(out["net_profit"], q["net_profit"])
        self.assertAlmostEqual(out["haul_cost"] - q["haul_cost"], 10_000_000.0)
        self.assertAlmostEqual(out["net_profit"], 90_000_000.0)

    def test_truthy_series_semantics(self):
        s = pd.Series([True, False, None], dtype="boolean")
        self.assertEqual(truthy_series(s).tolist(), [True, False, False])
        s2 = pd.Series(["true", "1", "yes", "false", None])
        self.assertEqual(truthy_series(s2).tolist(), [True, True, True, False, False])


if __name__ == "__main__":
    unittest.main()
