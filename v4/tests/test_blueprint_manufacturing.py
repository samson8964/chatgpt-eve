"""Blueprint manufacturing: exact per-run quantities, BOM depth, fee reserve and 3rd mail category."""
from __future__ import annotations

import json
import tarfile
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from v4.blueprint_manufacturing import evaluate_one, evaluate_blueprint_contract
from v4.blueprint_recipes import _entries, from_archive
from v4.engine import Order
from v4.unified_review import render, render_html


def book(t,p,n=100,buy=True):
    return [Order(order_id=(t*10+(1 if buy else 2)),
                  type_id=t,location_id=60003760,buy=buy,price=p,remaining=n)]


class BlueprintManufacturingTests(unittest.TestCase):
    def setUp(self):
        self.recipe={"materials":{"34":100,"35":1},"products":{"36":2},
                     "time_seconds":600}
        self.contract={"contract_id":1234567,"price":200_000_000,
                       "start_location_id":60008494,"type":"item_exchange"}
        self.bp={"type_id":101,"quantity":1,"is_blueprint_copy":True,
                 "runs":2,"material_efficiency":10,"time_efficiency":20}
        self.asks={34:book(34,100_000,10000,False),
                   35:book(35,1_000_000,10000,False)}
        self.bids={36:book(36,200_000_000,10000,True)}

    def test_bpc_bound_manufactured_output_cost_and_taxes(self):
        r=evaluate_one(self.contract,self.bp,self.recipe,self.asks,
                       self.bids,3_000_000)
        self.assertEqual(r["blueprint_kind"],"BPC")
        self.assertEqual(r["production_runs_assumed"],2)
        self.assertEqual(r["product_units"],4)
        self.assertEqual(r["required_materials"],{"34":180,"35":2})
        self.assertEqual(r["material_cost_isk"],20_000_000)
        self.assertEqual(r["manufacturing_fee_reserve_isk"],4_000_000)
        self.assertEqual(r["product_gross_isk"],800_000_000)
        self.assertEqual(r["sales_tax_isk"],27_000_000)
        self.assertEqual(r["cost"],227_000_000)
        self.assertEqual(r["net_profit"],546_000_000)
        self.assertGreater(r["roi"],.1)
        self.assertTrue(r["policy_passed"])

    def test_bpo_bounded_ten_runs_no_infinite_value(self):
        r=evaluate_one(self.contract,{**self.bp,"is_blueprint_copy":False,
                                      "runs":-1},self.recipe,
                       self.asks,self.bids,3_000_000)
        self.assertEqual(r["blueprint_kind"],"BPO")
        self.assertEqual(r["production_runs_assumed"],10)

    def test_bpc_cannot_use_more_than_one_licensed_run(self):
        r=evaluate_one(self.contract,{**self.bp,"runs":1},self.recipe,
                       self.asks,self.bids,0)
        self.assertEqual(r["production_runs_assumed"],1)

    def test_no_jita_material_ask_depth_no_blueprint_alert(self):
        missing={**self.asks,34:book(34,100_000,100,False)}
        self.assertIsNone(evaluate_one(self.contract,self.bp,self.recipe,missing,
                                       self.bids,0))
        self.assertIsNone(evaluate_one(self.contract,{**self.bp,
             "is_blueprint_copy":None},self.recipe,self.asks,self.bids,0))

    def test_recipe_activity_parses_eve_ref_material_maps(self):
        record={"100":{"activities":{"manufacturing":{
            "time":1200,
            "materials":{"34":{"type_id":34,"quantity":100},
                         "35":{"type_id":35,"quantity":1}},
            "products":{"36":{"type_id":36,"quantity":2}}
        }}}}
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"recipes.tar.xz"
            with tarfile.open(path,"w:xz") as archive:
                data=json.dumps(record).encode()
                info=tarfile.TarInfo("blueprints.json")
                info.size=len(data)
                archive.addfile(info,BytesIO(data))
            # normal production minimum >500; this fixture verifies only
            # parser's actual map layout, not production inventory size.
            self.assertEqual(_entries(record["100"]["activities"]["manufacturing"]
                                      ["materials"]),{"34":100,"35":1})


class BlueprintDigestTests(unittest.TestCase):
    def test_third_category_does_not_consume_other_two_quotas(self):
        sample={
            "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
            "source_input_integrity":"ALL_PARSED",
            "run_folder":"20261016T132301Z-abc",
            "market_research_leads":[],
            "contract_research_leads":[],
            "blueprint_research_leads":[{
                "contract_id":1234567,"blueprint_type_id":101,"blueprint_kind":"BPC",
                "production_runs_assumed":2,"product_type_id":36,"product_units":4,
                "net_profit_snapshot":546_000_000,"roi_snapshot":2.4,
                "material_cost":20_000_000,"fee_reserve":4_000_000,
                "source_location":60008494}],
        }
        subject,body=render(sample,game=False)
        self.assertIn("市场0 合同0 蓝图制造1",subject)
        self.assertIn("【蓝图制造（估算研究）】",body)
        self.assertIn("合同 1234567",body)
        hs,html=render_html(sample)
        self.assertEqual(subject,hs)
        self.assertIn("/c/1234567",html)
        self.assertIn("费用",html)


if __name__=="__main__":
    unittest.main()
