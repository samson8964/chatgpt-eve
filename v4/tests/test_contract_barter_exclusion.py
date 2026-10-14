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
            },{
                "order_id":1002,"type_id":34,"location_id":60008494,
                "is_buy_order":True,"price":11000000,"volume_remain":1000
            },{
                "order_id":1003,"type_id":34,"location_id":60008494,
                "is_buy_order":False,"price":1000000,"volume_remain":100
            }])
            contracts = pd.DataFrame([
                {"contract_id":101,"type":"item_exchange",
                 "start_location_id":60003760,"price":10000000,
                 "date_expired":"2030-01-01T00:00:00"},
                {"contract_id":102,"type":"item_exchange",
                 "start_location_id":60003760,"price":10000000,
                 "date_expired":"2030-01-01T00:00:00"},
                {"contract_id":103,"type":"item_exchange",
                 "start_location_id":60008494,"price":10000000,
                 "date_expired":"2030-01-01T00:00:00"},
            ])
            items=pd.DataFrame([
                {"contract_id":101,"is_included":True,"type_id":34,
                 "quantity":10,"is_blueprint_copy":False,"runs":-1},
                {"contract_id":101,"is_included":False,"type_id":36,
                 "quantity":10,"is_blueprint_copy":False,"runs":-1},
                {"contract_id":102,"is_included":True,"type_id":34,
                 "quantity":10,"is_blueprint_copy":False,"runs":-1},
                {"contract_id":103,"is_included":True,"type_id":34,
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
                  patch("v4.deep_scan.known_station_regions",return_value={}),
                  patch("v4.deep_scan.haul",side_effect=lambda source,dest,vol,stations: 0 if source==dest else 3000000) as haul_mock):
                report=deep_run(root/"orders",root/"contracts",output,api_key="")
            self.assertEqual(report["market_pricing_basis"],"JITA_4_4_BUY_DEPTH_SNAPSHOT")
            self.assertEqual(report["market_proofs_examined"],1)
            self.assertEqual(report["market_potential_pairs"],1)
            self.assertEqual(report["market_top5_price_definition"],
                "UNWEIGHTED_MEAN_OF_DISTINCT_PRICE_LEVELS")
            self.assertEqual(report["market_station_sell_census"]["4-H"]["active_sell_type_ids"],0)
            self.assertEqual(report["market_station_sell_census"]["O4T"]["active_sell_type_ids"],0)
            self.assertTrue(any(args.args[0]==60008494 and args.args[1]==60003760
                                and args.args[2]==100.0 for args in haul_mock.call_args_list))
            self.assertEqual(report["contract_requested_items_excluded"],1)
            self.assertEqual(report["contract_jita_examined"],1)
            self.assertEqual(report["contract_approved_locations_examined"],2)
            proofs=[json.loads(line) for line in
                    output.with_name("all_proofs.jsonl").read_text("utf-8").splitlines()]
            market_proofs=[p for p in proofs if p.get("kind")=="market"]
            self.assertEqual(len(market_proofs),1)
            self.assertEqual(market_proofs[0]["destination_location"],60003760)
            self.assertEqual(market_proofs[0]["cargo_volume_m3"],100.0)
            self.assertEqual(market_proofs[0]["valuation_location_id"],60003760)
            self.assertEqual(market_proofs[0]["source_top5_sell"]["group_count"],1)
            self.assertEqual(market_proofs[0]["jita_top5_buy"]["group_count"],1)
            self.assertEqual(market_proofs[0]["source_top5_sell"]["simple_mean_isk_per_unit"],1000000)
            self.assertEqual(market_proofs[0]["jita_top5_buy"]["simple_mean_isk_per_unit"],10000000)
            contract_ids=[p["contract_id"] for p in proofs if p.get("kind")=="contract"]
            self.assertEqual(contract_ids,[102,103])
            contract=next(p for p in proofs if p.get("kind")=="contract")
            self.assertEqual(contract["contract_price"],10000000)
            self.assertEqual(contract["included_items"],{"34":10})
            self.assertFalse(contract["requested_items_present"])
            self.assertEqual(contract["valuation_basis"],
                "JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE")
            amarr=next(p for p in proofs if p.get("contract_id")==103)
            self.assertEqual(amarr["source_location"],60008494)
            self.assertEqual(amarr["destination_location"],60003760)
            self.assertEqual(amarr["valuation_location_id"],60003760)
            self.assertEqual(amarr["haul_cost_estimate_isk"],3000000)
            self.assertEqual(amarr["gross"],100000000)
            self.assertFalse(amarr["contract_access_verified"])
            # Integration: a real deep_scan output must be accepted by the
            # combined digest reader, not just by isolated mocked fixtures.
            completed=root/"runs"/"20261014T122301Z-integration"
            completed.mkdir(parents=True)
            (completed/"deep_shadow.json").write_bytes(output.read_bytes())
            (completed/"all_proofs.jsonl").write_bytes(
                output.with_name("all_proofs.jsonl").read_bytes())
            (completed/"manifest.json").write_text(json.dumps({
                "status":"SHADOW_RECORDED",
                "mail_enabled":False,"ready_for_production":False,
                "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
                "source_input_integrity":"ALL_PARSED",
                "sqlite_unique_proofs":len(proofs)}),encoding="utf-8")
            from v4.unified_review import make_review, render
            unified=make_review(root)
            self.assertEqual(unified["market_proofs_examined"],1)
            self.assertEqual(unified["contract_proofs_audited"],2)
            subject,body=render(unified,game=True)
            self.assertIn("待核",subject)
            self.assertIn("快照待核",body)



if __name__ == "__main__":
    unittest.main()
