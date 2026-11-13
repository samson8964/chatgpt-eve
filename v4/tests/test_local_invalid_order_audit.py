import bz2
import csv
import json
import tempfile
import unittest
from pathlib import Path

from v4.local_invalid_order_audit import summarize


class OfflineInputAuditTests(unittest.TestCase):
    def test_uses_local_snapshot_and_proofs_no_network(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root/"runs"/"20261014T071050Z-cdc71ff3"
            (folder/"source").mkdir(parents=True)
            (folder/"deep_shadow.json").write_text(json.dumps({
                "source_input_integrity":"PARTIAL_QUARANTINED",
                "invalid_public_orders":1,
                "invalid_structure_orders":0,
            }),encoding="utf-8")
            with (folder/"all_proofs.jsonl").open("w",encoding="utf-8") as f:
                f.write(json.dumps({"reason":"SOURCE_ORDER_INVALID",
                     "source_lane":"PUBLIC","row_index":1,
                     "error_type":"ValueError","error_detail":"invalid_market_order",
                     "order_id_hint":"1001"})+"\n")
                f.write(json.dumps({"reason":"ITEM_CLASSIFICATION_UNVERIFIED_OR_BLUEPRINT"})+"\n")
            with bz2.open(folder/"source"/"market_orders.csv.bz2","wt",
                          encoding="utf-8",newline="") as f:
                writer=csv.DictWriter(f,fieldnames=[
                    "order_id","type_id","location_id","price",
                    "volume_remain","is_buy_order"])
                writer.writeheader()
                writer.writerow({"order_id":1000,"type_id":6,
                                 "location_id":60003760,"price":100.0,
                                 "volume_remain":1,"is_buy_order":"False"})
                writer.writerow({"order_id":1001,"type_id":6,
                                 "location_id":60003760,"price":0.0,
                                 "volume_remain":1,"is_buy_order":"False"})

            report=summarize(root,"20261014T071050Z-cdc71ff3")
            self.assertEqual(report["diagnostic_mode"],"OFFLINE_READ_ONLY")
            self.assertEqual(report["invalid_public_proofs_found"],1)
            self.assertTrue(report["proof_count_matches_report"])
            self.assertEqual(report["examples"][0]["source_fields"]["price"],"0.0")
            self.assertIsNone(report["examples"][0]["source_fields"]["min_volume"])
            self.assertFalse(report["sql_written"])
            self.assertFalse(report["mail_enabled"])

    def test_does_not_allow_path_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            for name in ("../", "..", "parent/child", "./", "."):
                with self.subTest(name=name):
                    with self.assertRaises(ValueError):
                        summarize(Path(td),name)


if __name__=="__main__":
    unittest.main()
