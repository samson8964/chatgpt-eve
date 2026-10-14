"""A requested contract item is not a free add-on in a cash-only valuation."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

try:
    import pandas as pd
    from v4.deep_scan import run as deep_run
except ImportError:
    pd = None
    deep_run = None


@unittest.skipUnless(pd is not None and deep_run is not None,
                     "requires optional pandas deep scan dependencies")
class V4ContractBarterExclusionTests(unittest.TestCase):
    def test_requested_item_contract_is_not_cash_only_opportunity(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            orders = pd.DataFrame([{
                "order_id":1001,"type_id":34,"location_id":60003760,
                "is_buy_order":True,"price":10000000,"volume_remain":1000
            }])
            contracts = pd.DataFrame([
                {"contract_id":101,"type":"item_exchange",
                 "start_location_id":60003760,"price":10000000,
                 "date_expired":"2030-01-01T00:00:00"},
                {"contract_id":102,"type":"item_exchange",
                 "start_location_id":60003760,"price":10000000,
                 "date_expired":"2030-01-01T00:00:00"},
            ])
            items=pd.DataFrame([
                {"contract_id":101,"is_included":True,"type_id":34,
                 "quantity":10,"is_blueprint_copy":False,"runs":-1},
                {"contract_id":101,"is_included":False,"type_id":36,
                 "quantity":10,"is_blueprint_copy":False,"runs":-1},
                {"contract_id":102,"is_included":True,"type_id":34,
                 "quantity":10,"is_blueprint_copy":False,"runs":-1},
            ])
            catalog=Mock()
            catalog.volume.return_value=1.0
            catalog.classification.return_value="regular"
            catalog.coverage.return_value={"missing_volume":[]}
            catalog.meta={"fixture":True}
            output=root/"deep_shadow.json"
            with (patch("v4.deep_scan.market_dataframe",return_value=orders),
                  patch("v4.deep_scan.contract_dataframes",return_value=(contracts,items)),
                  patch("v4.deep_scan.all_structure_orders",return_value=(
                      [],{"four_h":{"status":"COMPLETE","location":1053970513596},
                          "cj":{"status":"COMPLETE","location":1049588174021},
                          "o4t":{"status":"COMPLETE","location":1040804972352}})),
                  patch("v4.deep_scan.ensure_catalog",return_value=catalog),
                  patch("v4.deep_scan.known_station_regions",return_value={})):
                report=deep_run(root/"orders",root/"contracts",output,api_key="")
            self.assertEqual(report["contract_requested_items_excluded"],1)
            self.assertEqual(report["contract_jita_examined"],1)
            proofs=[json.loads(line) for line in
                    output.with_name("all_proofs.jsonl").read_text("utf-8").splitlines()]
            contract_ids=[p["contract_id"] for p in proofs if p.get("kind")=="contract"]
            self.assertEqual(contract_ids,[102])
            contract=next(p for p in proofs if p.get("kind")=="contract")
            self.assertEqual(contract["contract_price"],10000000)
            self.assertEqual(contract["included_items"],{"34":10})
            self.assertFalse(contract["requested_items_present"])
            self.assertEqual(contract["valuation_basis"],
                "JITA_SNAPSHOT_BUY_ORDER_DEPTH_NOT_LIVE")


if __name__ == "__main__":
    unittest.main()
