"""End-to-end structure SKU census and top-five source/Jita quotes in deep_scan."""
from __future__ import annotations

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
                     "requires pandas for complete deep-scan integration")
class StationDepthIntegration(unittest.TestCase):
    def test_four_h_all_skus_o4t_no_jita_and_five_real_levels(self):
        h = 1053970513596
        o = 1040804972352
        jita = 60003760
        source = []
        for i, price in enumerate((10e6,10e6,9e6,8e6,7e6,6e6),start=1):
            source.append({
                "order_id":i,"type_id":41058,"location_id":jita,
                "is_buy_order":True,"price":price,"volume_remain":150,
            })
        structures = []
        for i, price in enumerate((1e6,2e6,2e6,3e6,4e6,5e6,6e6),start=101):
            structures.append({
                "order_id":i,"type_id":41058,"location_id":h,
                "is_buy_order":False,"price":price,"volume_remain":20,
            })
        structures.extend([
            {"order_id":201,"type_id":41058,"location_id":o,
             "is_buy_order":False,"price":12e6,"volume_remain":20},
            {"order_id":202,"type_id":3333,"location_id":o,
             "is_buy_order":False,"price":3e6,"volume_remain":20},
        ])
        health={
            "four_h":{"status":"COMPLETE","location":h,"orders":7},
            "cj":{"status":"COMPLETE","location":1049588174021,"orders":0},
            "o4t":{"status":"COMPLETE","location":o,"orders":2},
        }
        contracts = pd.DataFrame(columns=["contract_id","type","start_location_id","price"])
        items = pd.DataFrame(columns=[
            "contract_id","is_included","type_id","quantity",
            "is_blueprint_copy","runs"])
        catalog=Mock()
        catalog.volume.return_value=1.0
        catalog.classification.return_value="regular"
        catalog.coverage.return_value={"missing_volume":[]}
        catalog.meta={"fixture":True}
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            deep=root/"runs"/"20261014T130000Z-fixture"/"deep_shadow.json"
            deep.parent.mkdir(parents=True)
            with (
                patch("v4.deep_scan.market_dataframe",return_value=pd.DataFrame(source)),
                patch("v4.deep_scan.contract_dataframes",
                      return_value=(contracts,items)),
                patch("v4.deep_scan.all_structure_orders",
                      return_value=(structures,health)),
                patch("v4.deep_scan.ensure_catalog",return_value=catalog),
                patch("v4.deep_scan.known_station_regions",return_value={}),
                patch("v4.deep_scan.haul",return_value=1000000),
            ):
                report=deep_run(root/"market",root/"contract",deep,api_key="")
            a=report["market_station_sell_census"]
            self.assertEqual(a["4-H"]["active_sell_type_ids"],1)
            self.assertEqual(a["4-H"]["active_sell_orders"],7)
            self.assertEqual(a["4-H"]["sell_types_with_jita_buy"],1)
            self.assertEqual(a["4-H"]["sell_types_optimistic_gate_passed"],1)
            self.assertEqual(a["O4T"]["active_sell_type_ids"],2)
            self.assertEqual(a["O4T"]["sell_types_with_jita_buy"],1)
            self.assertEqual(a["O4T"]["sell_types_without_jita_buy"],1)
            self.assertEqual(a["O4T"]["sell_types_optimistic_gate_passed"],0)
            self.assertEqual(report["market_proofs_examined"],1)
            self.assertEqual(report["market_prefilter_basis"],
                             "TWO_SIDED_MATCHED_DEPTH_GROSS_MARGIN_BEFORE_FEES")
            proofs=[json.loads(line) for line in
                    (deep.parent/"all_proofs.jsonl").read_text("utf-8").splitlines()]
            market=[p for p in proofs if p.get("kind")=="market"]
            self.assertEqual(len(market),1)
            self.assertEqual(market[0]["source_location"],h)
            self.assertEqual(market[0]["source_top5_sell"]["group_count"],5)
            self.assertEqual(market[0]["source_top5_sell"]["simple_mean_isk_per_unit"],3e6)
            self.assertEqual(market[0]["jita_top5_buy"]["group_count"],5)
            self.assertEqual(market[0]["jita_top5_buy"]["simple_mean_isk_per_unit"],8e6)
            self.assertTrue(market[0]["quantity_optimized"])
            self.assertEqual(market[0]["source_vwap_isk_per_unit"],
                             market[0]["executed_sell_cost"]/market[0]["quantity"])
            self.assertEqual(market[0]["jita_vwap_isk_per_unit"],
                             market[0]["executed_jita_buy_gross"]/market[0]["quantity"])
            manifest={"status":"SHADOW_RECORDED","mail_enabled":False,
                      "ready_for_production":False,"coverage_gate":
                      "INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
                      "source_input_integrity":"ALL_PARSED"}
            (deep.parent/"manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
            from v4.unified_review import make_review,render
            # Synthetic integration scan has a mocked in-memory catalog and
            # deliberately no installed SDE file. The real production mail
            # path remains fail-closed when a scan catalog cannot be loaded.
            with patch("v4.contract_review.load_policy_for_run",return_value=None), \
                 patch("v4.unified_review.load_policy_for_run",return_value=None):
                unified=make_review(root)
            self.assertEqual(unified["market_research_leads_total"],1)
            _,mail=render(unified,game=True)
            self.assertIn("成交均 本地卖",mail)
            self.assertIn("卖5档均0.03亿",mail)
            self.assertIn("吉买5档均0.08亿",mail)
            from v4.market_station_audit import summarize
            historical=summarize(root)
            self.assertEqual(historical["stations"]["4-H"]["active_sell_type_ids"],1)
            self.assertEqual(historical["stations"]["O4T"]["active_sell_type_ids"],2)


if __name__=="__main__":
    unittest.main()
