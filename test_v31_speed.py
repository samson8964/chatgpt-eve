from __future__ import annotations

import json
import tarfile
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

import scanner_source as src
import four_h_contract_scanner as four_h
import structure_market_arbitrage as four_h_market


class V31SpeedTests(unittest.TestCase):
    def setUp(self):
        self._cache = src.CACHE
        self._parsed = src.V31_PARSED_CACHE_DIR
        self._fh_cache = four_h.V31_STRUCTURE_ORDERS_CACHE
        self._fh_age = four_h.V31_STRUCTURE_CACHE_MAX_AGE
        self._fh_market_cache = four_h_market.V31_STRUCTURE_ORDERS_CACHE
        self._fh_market_age = four_h_market.V31_STRUCTURE_CACHE_MAX_AGE

    def tearDown(self):
        src.CACHE = self._cache
        src.V31_PARSED_CACHE_DIR = self._parsed
        four_h.V31_STRUCTURE_ORDERS_CACHE = self._fh_cache
        four_h.V31_STRUCTURE_CACHE_MAX_AGE = self._fh_age
        four_h_market.V31_STRUCTURE_ORDERS_CACHE = self._fh_market_cache
        four_h_market.V31_STRUCTURE_CACHE_MAX_AGE = self._fh_market_age

    def test_truthy_series_handles_nullable_boolean_and_strings(self):
        b = pd.Series([True, False, None], dtype="boolean")
        self.assertEqual(src.truthy_series(b).tolist(), [True, False, False])
        s = pd.Series(["true", "1", "YES", None, "false"], dtype="object")
        self.assertEqual(src.truthy_series(s).tolist(), [True, True, True, False, False])

    def test_parsed_snapshot_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src.V31_PARSED_CACHE_DIR = str(root / "parsed")

            market_path = root / "market.csv.bz2"
            expected_market = pd.DataFrame({"type_id": [1, 2], "price": [3.5, 4.5]})
            expected_market.to_csv(market_path, index=False, compression="bz2")
            first_market = src.load_market_orders(market_path)
            second_market = src.load_market_orders(market_path)
            pd.testing.assert_frame_equal(first_market, second_market)

            contracts_csv = root / "contracts.csv"
            items_csv = root / "contract_items.csv"
            pd.DataFrame({"contract_id": [10], "type": ["item_exchange"]}).to_csv(contracts_csv, index=False)
            pd.DataFrame({"contract_id": [10], "type_id": [34], "quantity": [100]}).to_csv(items_csv, index=False)
            archive = root / "contracts.tar.bz2"
            with tarfile.open(archive, "w:bz2") as tf:
                tf.add(contracts_csv, arcname="snapshot/contracts.csv")
                tf.add(items_csv, arcname="snapshot/contract_items.csv")

            c1, i1 = src.load_contracts(archive)
            c2, i2 = src.load_contracts(archive)
            pd.testing.assert_frame_equal(c1, c2)
            pd.testing.assert_frame_equal(i1, i2)

            pickles = list((root / "parsed").glob("*.pkl"))
            self.assertGreaterEqual(len(pickles), 3)

    def test_atomic_reference_cache_survives_concurrent_writers(self):
        with tempfile.TemporaryDirectory() as td:
            src.CACHE = Path(td) / "cache"
            payloads = [{"value": i} for i in range(24)]
            with ThreadPoolExecutor(max_workers=8) as ex:
                list(ex.map(lambda p: src.cache_put("types", 12345, p), payloads))
            final = src.cache_get("types", 12345)
            self.assertIsInstance(final, dict)
            self.assertIn("value", final)
            self.assertIn(final["value"], range(24))

    def test_shared_four_h_snapshot_is_reused_by_both_scanners(self):
        rows = [
            {"type_id": 34, "price": 3.1, "volume_remain": 1000, "min_volume": 1, "is_buy_order": False, "order_id": 1},
            {"type_id": 34, "price": 3.8, "volume_remain": 500, "min_volume": 1, "is_buy_order": True, "order_id": 2},
        ]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "four_h.json"
            path.write_text(json.dumps({"structure_id": four_h.STRUCTURE_ID, "orders": rows}), "utf-8")

            four_h.V31_STRUCTURE_ORDERS_CACHE = str(path)
            four_h.V31_STRUCTURE_CACHE_MAX_AGE = 3600
            loaded = four_h.fetch_structure_orders()
            self.assertEqual(loaded, rows)

            four_h_market.V31_STRUCTURE_ORDERS_CACHE = str(path)
            four_h_market.V31_STRUCTURE_CACHE_MAX_AGE = 3600
            sells, count, _ = four_h_market.load_four_h_sells()
            self.assertEqual(count, 2)
            self.assertEqual(len(sells[34]), 1)
            self.assertEqual(sells[34][0]["price"], 3.1)


if __name__ == "__main__":
    unittest.main()
