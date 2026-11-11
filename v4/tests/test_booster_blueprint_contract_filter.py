"""End-to-end shadow-only Booster Blueprint group-718 exclusion proof."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

try:
    import pandas as pd
    from v4.deep_scan import run as run_deep
except ImportError:
    pd = None
    run_deep = None


@unittest.skipUnless(pd is not None and run_deep is not None,
                     "optional pandas deep scan dependencies unavailable")
class BoosterBlueprintDeepExclusionTests(unittest.TestCase):
    def test_mixed_contract_excluded_from_both_cash_and_bpc_even_with_profitable_goods(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            orders=pd.DataFrame([{
                "order_id":11,"location_id":60003760,"type_id":34,
                "is_buy_order":True,"price":200_000_000,
                "volume_remain":100,"min_volume":1,"range":"station",
            }])
            contracts=pd.DataFrame([
                {"contract_id":701,"type":"item_exchange",
                 "start_location_id":60003760,"price":100_000_000,
                 "date_expired":"2030-01-01T00:00:00"},
                {"contract_id":702,"type":"item_exchange",
                 "start_location_id":60003760,"price":100_000_000,
                 "date_expired":"2030-01-01T00:00:00"},
            ])
            items=pd.DataFrame([
                {"contract_id":701,"is_included":True,"type_id":34,
                 "quantity":1,"is_blueprint_copy":False,"runs":-1},
                {"contract_id":701,"is_included":True,"type_id":25327,
                 "quantity":1,"is_blueprint_copy":True,"runs":10},
                {"contract_id":702,"is_included":True,"type_id":34,
                 "quantity":1,"is_blueprint_copy":False,"runs":-1},
            ])
            catalog=Mock()
            catalog.volume.side_effect=lambda t: .01 if int(t)==25327 else 1.0
            catalog.group_id.side_effect=lambda t: 718 if int(t)==25327 else 18
            catalog.classification.side_effect=lambda t: (
                "blueprint_type" if int(t)==25327 else "regular")
            catalog.coverage.return_value={"missing_volume":[]}
            catalog.meta={"type_count":2}
            output=root/"deep_shadow.json"
            health={"cj":{"status":"COMPLETE","location":1049588174021,
                          "orders":0,"pages":1},
                    "o4t":{"status":"COMPLETE","location":1040804972352,
                           "orders":0,"pages":1}}
            bp_recipe={"25327":{"materials":{"34":1},"products":{"34":1},
                                 "time_seconds":600}}
            with patch("v4.deep_scan.market_dataframe",return_value=orders), \\
                 patch("v4.deep_scan.contract_dataframes",
                       return_value=(contracts,items)), \\
                 patch("v4.deep_scan.all_structure_orders",
                       return_value=([],health)), \\
                 patch("v4.deep_scan.ensure_catalog",return_value=catalog), \\
                 patch("v4.deep_scan.known_station_regions",return_value={}), \\
                 patch("v4.deep_scan.load_blueprint_recipes",
                       return_value={"manufacturing_recipes":bp_recipe}), \\
                 patch("v4.deep_scan.load_jita_npc_fee_context",
                       return_value=None), \\
                 patch("v4.deep_scan.evaluate_blueprint_contract") as bp_eval:
                report=run_deep(root/"market",root/"contracts",output)
            proof_file=output.with_name("all_proofs.jsonl")
            proofs=[json.loads(x) for x in proof_file.read_text("utf-8").splitlines()]
            excluded=[p for p in proofs if p.get("contract_id")==701]
            retained=[p for p in proofs if p.get("contract_id")==702]
            self.assertEqual(len(excluded),1)
            self.assertEqual(excluded[0]["reason"],
                             "BOOSTER_BLUEPRINT_CONTRACT_EXCLUDED")
            self.assertFalse(excluded[0]["model_candidate"])
            self.assertEqual(excluded[0]["status"],"WATCH")
            self.assertEqual(len(retained),1)
            bp_eval.assert_not_called()
            self.assertEqual(report["booster_blueprint_contracts_excluded"],1)
            self.assertEqual(report["contract_approved_locations_examined"],2)


if __name__=="__main__":
    unittest.main()
