"""NPC trade hub diagnostics: coverage is snapshot presence, not live ESI."""
import bz2
import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from v4.npc_hub_health import HUBS, from_orders, inspect_csv


class NPCHubHealthTests(unittest.TestCase):
    def test_all_three_trade_hubs_and_74l2_is_not_mislabelled_npc(self):
        orders = [
            SimpleNamespace(location_id=60003760, type_id=34, buy=True),
            SimpleNamespace(location_id=60003760, type_id=34, buy=False),
            SimpleNamespace(location_id=60008494, type_id=35, buy=True),
            SimpleNamespace(location_id=60008494, type_id=35, buy=False),
            SimpleNamespace(location_id=60011866, type_id=36, buy=True),
            SimpleNamespace(location_id=60011866, type_id=37, buy=False),
            SimpleNamespace(location_id=1050474463169, type_id=34, buy=False),
        ]
        result = from_orders(orders)
        self.assertEqual(set(result), {"jita", "amarr", "dodixie"})
        self.assertEqual([result[name]["active_orders"] for name in HUBS],
                         [2, 2, 2])
        self.assertTrue(all(
            result[name]["status"] == "BOTH_SIDES_PRESENT_IN_PUBLIC_SNAPSHOT"
            for name in HUBS))
        self.assertEqual(result["jita"]["role"], "BUY_DEPTH_VALUATION_BENCHMARK")
        self.assertEqual(result["amarr"]["role"], "APPROVED_SOURCE_MARKET")
        self.assertNotIn("banestar", result)

    def test_awaiting_public_orders_is_not_falsely_complete(self):
        orders = [SimpleNamespace(location_id=60008494, type_id=123, buy=False)]
        result = from_orders(orders)
        self.assertEqual(result["amarr"]["status"],
                         "ONE_SIDE_ONLY_IN_PUBLIC_SNAPSHOT")
        self.assertEqual(result["dodixie"]["status"],
                         "NO_ACTIVE_ORDERS_IN_PUBLIC_SNAPSHOT")
        self.assertEqual(result["jita"]["active_orders"], 0)
        self.assertEqual(result["dodixie"]["station_page_coverage"],
                         "NOT_PROVIDED_BY_PUBLIC_SNAPSHOT")

    def test_streaming_csv_has_same_counts_and_no_file_mutations(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "market_orders.csv.bz2"
            with bz2.open(path, "wt", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["location_id", "type_id", "price",
                                   "volume_remain", "is_buy_order"])
                writer.writeheader()
                for row in [
                    (60003760, 34, "100", 1, "True"),
                    (60003760, 34, "110", 1, "False"),
                    (60008494, 35, "110", 10, "True"),
                    (60008494, 35, "111", 10, "False"),
                    (60011866, 36, "110", 1, "True"),
                    (60011866, 36, "111", 1, "False"),
                    (60011866, 36, "111", 0, "False"),
                    (1050474463169, 34, "110", 10, "False"),
                ]:
                    writer.writerow(dict(zip(writer.fieldnames, row)))
            before = path.read_bytes()
            r = inspect_csv(path)
            self.assertEqual(r["amarr"]["active_buy_orders"], 1)
            self.assertEqual(r["dodixie"]["active_sell_orders"], 1)
            self.assertEqual(r["jita"]["active_orders"], 2)
            self.assertEqual(path.read_bytes(), before)

    def test_missing_or_malformed_archive_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "ARCHIVE_INVALID"):
                inspect_csv(Path(td) / "missing.csv.bz2")
            with bz2.open(Path(td) / "bad.csv.bz2", "wt") as f:
                f.write("missing,columns\n1,2\n")
            with self.assertRaisesRegex(ValueError, "COLUMNS_MISSING"):
                inspect_csv(Path(td) / "bad.csv.bz2")


if __name__ == "__main__":
    unittest.main()
