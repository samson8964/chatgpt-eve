"""Unified V4 contract/mkt/blueprint mail quotas remain independent."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v4.unified_review import make_review, render


class TripleMailQuotaTests(unittest.TestCase):
    def test_blueprint_ten_does_not_consume_contract_or_market_slots(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            folder=root/"runs"/"20261016T152301Z-testbp"
            folder.mkdir(parents=True)
            (folder/"manifest.json").write_text(json.dumps({
                "status":"SHADOW_RECORDED",
                "mail_enabled":False,
                "ready_for_production":False,
                "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
                "source_input_integrity":"ALL_PARSED"}))
            (folder/"deep_shadow.json").write_text(json.dumps({
                "status":"SHADOW_ONLY_NO_LIVE_ALERTS",
                "market_pricing_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT",
                "market_execution_basis":"OPTIMIZED_MATCHED_QUANTITY_AND_VWAP",
                "market_proofs_examined":0,
                "contract_approved_locations_examined":0,
                "contract_pricing_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT",
                "blueprint_manufacturing_recipe_status":"INSTALLED"
            }))
            data=[]
            for i in range(15):
                data.append({
                    "kind":"blueprint_manufacturing","status":"WATCH",
                    "reason":"BLUEPRINT_MANUFACTURING_MODEL_ESTIMATE_FEE_UNVERIFIED",
                    "model_candidate":True,
                    "valuation_basis":"JITA_BUY_FINISHED_GOODS_JITA_SELL_MATERIALS_SNAPSHOT",
                    "facility_fee_status":"20_PERCENT_MATERIAL_COST_RESERVE_NOT_FACILITY_VERIFIED",
                    "jita_material_ask_depth_verified_in_snapshot":True,
                    "jita_product_buy_depth_verified_in_snapshot":True,
                    "contract_id":123456+i,
                    "blueprint_type_id":100+i,
                    "blueprint_kind":"BPC",
                    "material_efficiency":0,
                    "production_runs_assumed":1,
                    "product_type_id":200+i,
                    "product_units":1,
                    "contract_price_isk":10_000_000,
                    "material_cost_isk":20_000_000,
                    "manufacturing_fee_reserve_isk":4_000_000,
                    "sales_tax_isk":1_000_000,
                    "net_profit":100_000_000+i,
                    "roi":2.0,
                    "source_location":60003760,
                })
            (folder/"all_proofs.jsonl").write_text(
                "".join(json.dumps(x)+"\n" for x in data),encoding="utf-8")
            review=make_review(root)
            self.assertEqual(review["market_research_leads_total"],0)
            self.assertEqual(review["contract_research_leads_total"],0)
            self.assertEqual(review["blueprint_research_leads_total"],15)
            self.assertEqual(len(review["blueprint_research_leads"]),10)
            self.assertEqual(len(review["market_research_leads"]),0)
            self.assertEqual(len(review["contract_research_leads"]),0)
            subject,body=render(review)
            self.assertIn("市场0 合同0 蓝图制造10",subject)
            self.assertIn("蓝图制造",body)


if __name__ == "__main__":
    unittest.main()
