from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest

import pandas as pd
from pathlib import Path
from unittest.mock import patch

from run_cache_v31 import cached_market_json, stats


class RunCacheV31Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache_dir = str(Path(self.tmp.name) / "cache")
        self.env = patch.dict(os.environ, {"EVE_RUN_CACHE_DIR": self.cache_dir}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_single_flight_same_market_request(self):
        counter = {"n": 0}
        guard = threading.Lock()

        def fetcher():
            with guard:
                counter["n"] += 1
            time.sleep(0.12)
            return [{"x": 1}], {"X-Pages": "1"}

        out = []

        def worker():
            out.append(
                cached_market_json(
                    "https://esi.evetech.net/latest/markets/10000002/orders/",
                    {"type_id": 34, "order_type": "buy", "page": 1},
                    fetcher,
                )
            )

        threads = [threading.Thread(target=worker) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(counter["n"], 1)
        self.assertEqual(len(out), 6)
        self.assertTrue(all(x[0] == [{"x": 1}] for x in out))
        s = stats()
        self.assertEqual(s.get("misses"), 1)
        self.assertEqual(s.get("writes"), 1)
        self.assertEqual(s.get("hits"), 5)

    def test_page_and_side_are_distinct_keys(self):
        counter = {"n": 0}

        def fetcher():
            counter["n"] += 1
            return [{"n": counter["n"]}], {"X-Pages": "2"}

        base = "https://esi.evetech.net/latest/markets/10000002/orders/"
        cached_market_json(base, {"type_id": 34, "order_type": "buy", "page": 1}, fetcher)
        cached_market_json(base, {"type_id": 34, "order_type": "buy", "page": 2}, fetcher)
        cached_market_json(base, {"type_id": 34, "order_type": "sell", "page": 1}, fetcher)
        self.assertEqual(counter["n"], 3)

    def test_industry_cost_quote_is_cached_by_full_parameters(self):
        counter = {"n": 0}

        def fetcher():
            counter["n"] += 1
            return {"manufacturing": {"34": {"total_job_cost": 1}}}, {}

        url = "https://api.everef.net/v1/industry/cost"
        params = {"blueprint_id": 1, "product_id": 34, "runs": 10, "system_id": 30000142}
        first = cached_market_json(url, params, fetcher)
        second = cached_market_json(url, dict(reversed(list(params.items()))), fetcher)
        self.assertEqual(counter["n"], 1)
        self.assertEqual(first[0], second[0])

    def test_non_market_requests_are_not_cached(self):
        counter = {"n": 0}

        def fetcher():
            counter["n"] += 1
            return {"ok": True}, {}

        url = "https://example.test/other"
        cached_market_json(url, {}, fetcher)
        cached_market_json(url, {}, fetcher)
        self.assertEqual(counter["n"], 2)


class SharedSnapshotV31Tests(unittest.TestCase):
    def test_latest_file_uses_manifest_without_network(self):
        import scanner_source

        with tempfile.TemporaryDirectory() as td:
            manifest = Path(td) / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "datasets": {
                            "public_contracts": {
                                "source_url": "https://example.test/contracts.tar.bz2",
                                "last_modified": "2026-09-19T00:00:00Z",
                            },
                            "market_orders": {
                                "source_url": "https://example.test/orders.csv.bz2",
                                "last_modified": "2026-09-19T00:01:00Z",
                            },
                        }
                    }
                ),
                "utf-8",
            )
            with patch.dict(os.environ, {"EVE_RUN_SNAPSHOT_MANIFEST": str(manifest)}, clear=False):
                with patch.object(scanner_source, "get_json", side_effect=AssertionError("network should not be used")):
                    c = scanner_source.latest_file(scanner_source.PUBLIC_CONTRACTS_INDEX)
                    m = scanner_source.latest_file(scanner_source.MARKET_ORDERS_INDEX)
            self.assertEqual(c[0], "https://example.test/contracts.tar.bz2")
            self.assertEqual(m[0], "https://example.test/orders.csv.bz2")

    def test_four_h_scanners_share_local_snapshot(self):
        import four_h_contract_scanner
        import structure_market_arbitrage

        rows = [
            {
                "type_id": 34,
                "price": 3.0,
                "volume_remain": 100,
                "min_volume": 1,
                "is_buy_order": False,
                "order_id": 1,
            },
            {
                "type_id": 34,
                "price": 4.0,
                "volume_remain": 50,
                "min_volume": 1,
                "is_buy_order": True,
                "order_id": 2,
            },
        ]
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "four_h.json"
            p.write_text(json.dumps(rows), "utf-8")
            with patch.dict(
                os.environ,
                {
                    "EVE_RUN_4H_ORDERS_PATH": str(p),
                    "EVE_RUN_4H_EXPIRES": "test-expiry",
                },
                clear=False,
            ):
                got = four_h_contract_scanner.fetch_structure_orders()
                sells, count, expires = structure_market_arbitrage.load_four_h_sells()
            self.assertEqual(got, rows)
            self.assertEqual(count, 2)
            self.assertEqual(expires, "test-expiry")
            self.assertIn(34, sells)


class CompatibilityV31Tests(unittest.TestCase):
    def test_truthy_series_preserves_boolean_and_string_semantics(self):
        import scanner_source

        bools = pd.Series([True, False, None], dtype="boolean")
        strings = pd.Series(["TRUE", "1", "yes", "false", None], dtype="object")
        self.assertEqual(scanner_source.truthy_series(bools).tolist(), [True, False, False])
        self.assertEqual(scanner_source.truthy_series(strings).tolist(), [True, True, True, False, False])

    def test_mail_preflight_fails_before_any_sender_when_env_missing(self):
        import v31_finalize

        with patch.dict(
            os.environ,
            {
                "V31_SEND_MAIL": "1",
                "EVE_MAIL_API_KEY": "",
                "EVE_MAIL_WORKER_URL": "",
                "EVE_MAIL_RECIPIENT_NAMES": "",
            },
            clear=False,
        ):
            with patch.object(v31_finalize.subprocess, "run", side_effect=AssertionError("mail sender must not start")):
                with self.assertRaisesRegex(RuntimeError, "mail preflight missing"):
                    v31_finalize.run_mail_once()


if __name__ == "__main__":
    unittest.main()
