"""Offline proof/report regression for V4 snapshots with zero-remaining orders."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from v4.deep_scan import run as deep_run


class NonActionableOrderAuditTests(unittest.TestCase):
    def _run(self, volume, price):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            def order(order_id, remaining, order_price):
                return dict(order_id=order_id,type_id=482,location_id=60003760,
                            price=order_price,volume_remain=remaining,
                            min_volume=1,is_buy_order=False,range="region")
            market=pd.DataFrame([order(1,10,1000.0),
                                 order(7444436938,volume,price)])
            contracts=pd.DataFrame(columns=["type","start_location_id","contract_id"])
            items=pd.DataFrame(columns=["is_included","contract_id","type_id",
                                        "quantity","is_blueprint_copy","runs"])
            catalog=Mock()
            catalog.coverage.return_value={"missing_volume":[]}
            catalog.meta={"fixture":True}
            output=folder/"deep_shadow.json"
            with (patch("v4.deep_scan.market_dataframe",return_value=market),
                  patch("v4.deep_scan.contract_dataframes",return_value=(contracts,items)),
                  patch("v4.deep_scan.all_structure_orders",return_value=(
                      [],{name:{"status":"COMPLETE","location":location,
                               "orders":0,"pages":1,"pages_fetched":1}
                          for name,location in
                          (("four_h",1053970513596),("cj",1049588174021),
                           ("o4t",1040804972352))})),
                  patch("v4.deep_scan.ensure_catalog",return_value=catalog),
                  patch("v4.deep_scan.known_station_regions",return_value={})):
                result=deep_run(folder/"source.csv",folder/"contracts.tar",output,api_key="")
            proofs=[json.loads(line) for line in
                    output.with_name("all_proofs.jsonl").read_text("utf-8").splitlines()]
            self.assertEqual(result["proof_count"],len(proofs))
            self.assertEqual(sum(result["reason_counts"].values()),len(proofs))
            self.assertEqual(result["public_market_rows_raw"],2)
            return result,proofs

    def test_zero_remaining_does_not_downgrade_complete_input(self):
        report,proofs=self._run(0,518100.0)
        self.assertEqual(report["source_input_integrity"],"ALL_PARSED")
        self.assertEqual(report["invalid_public_orders"],0)
        self.assertEqual(report["zero_remaining_public_orders"],1)
        self.assertEqual(report["public_market_orders"],1)
        self.assertEqual(report["reason_counts"].get("SOURCE_ORDER_ZERO_REMAINING"),1)
        self.assertTrue(all(p["status"]=="RESEARCH" for p in proofs))

    def test_zero_remaining_with_bad_price_still_quarantines(self):
        report,proofs=self._run(0,-10.0)
        self.assertEqual(report["source_input_integrity"],"PARTIAL_QUARANTINED")
        self.assertEqual(report["invalid_public_orders"],1)
        self.assertEqual(report["zero_remaining_public_orders"],0)
        self.assertEqual(report["reason_counts"].get("SOURCE_ORDER_INVALID"),1)

    def test_negative_remaining_still_quarantines(self):
        report,proofs=self._run(-1,1000.0)
        self.assertEqual(report["source_input_integrity"],"PARTIAL_QUARANTINED")
        self.assertEqual(report["invalid_public_orders"],1)
        self.assertEqual(report["zero_remaining_public_orders"],0)


if __name__=="__main__":
    unittest.main()
