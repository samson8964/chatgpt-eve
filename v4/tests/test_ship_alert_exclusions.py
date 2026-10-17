"""Capital/freighter V4 research-mail exclusion across all three categories.

Only official item inventory group IDs and manufacturing recipe product links
are authoritative. Never infer a blocked class from a translation or name.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v4.catalog import Catalog
from v4.ship_alert_exclusions import (
    CAPITAL_GROUPS, FREIGHTER_GROUPS, BLOCKED_SHIP_GROUPS, POLICY_NAME,
    build_policy, load_policy_for_run
)
from v4.unified_review import make_review, render, render_html
from v4.contract_review import make_review as standalone_contract_review

MARKET_BASIS="JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE"
BLUEPRINT_BASIS="JITA_BUY_FINISHED_GOODS_JITA_SELL_MATERIALS_SNAPSHOT"


def catalogue():
    items={
        "34":[0.01,"regular",18],            # non-cap material
        "101":[1000,"regular",513],          # Freighter
        "102":[1000,"regular",902],          # Jump Freighter
        "103":[1000,"regular",485],          # Dreadnought
        "104":[1000,"regular",5120],         # Command Carrier
        "105":[1000,"regular",4594],         # Lancer Dreadnought
        "106":[1000,"regular",30],           # Titan
        "107":[1000,"regular",883],          # Capital Industrial Ship
        "108":[1000,"regular",659],          # Supercarrier
        "109":[1000,"regular",1538],         # Force Auxiliary
        "110":[1000,"regular",547],          # Carrier
        "111":[400,"regular",27],            # subcapital battleship
        "201":[0.01,"blueprint_type",9],     # capital blueprint -> hull 103
        "202":[0.01,"blueprint_type",9],     # subcap blueprint -> hull 111
        "203":[0.01,"blueprint_type",9],     # unknown blueprint
    }
    return Catalog(items,{"type_count":len(items),"sha256":"fixture-sha"})


def recipes():
    return {"manufacturing_recipes":{
        "201":{"products":{"103":1},"materials":{"34":10}},
        "202":{"products":{"111":1},"materials":{"34":10}},
    }}


def market(type_id):
    return {
        "kind":"market","model_candidate":True,"status":"WATCH",
        "source_location":1049588174021,"destination_location":60003760,
        "valuation_location_id":60003760,"valuation_basis":MARKET_BASIS,
        "type_id":type_id,"quantity":1,"profit":90_000_000,"roi":.3,
        "quantity_optimized":True,
        "source_vwap_isk_per_unit":100_000_000,
        "jita_vwap_isk_per_unit":200_000_000,
        "executed_sell_cost":100_000_000,"executed_jita_buy_gross":200_000_000,
        "stress_profit":60_000_000,"cost":100_000_000,
        "reason":"LIVE_ORDER_AND_CONTRACT_NOT_REVALIDATED"}


def blueprint(cid,blueprint_type,product_type):
    return {
        "kind":"blueprint_manufacturing","status":"WATCH",
        "reason":"BLUEPRINT_MANUFACTURING_MODEL_ESTIMATE_FEE_UNVERIFIED",
        "model_candidate":True,"valuation_basis":BLUEPRINT_BASIS,
        "facility_fee_status":"20_PERCENT_MATERIAL_COST_RESERVE_NOT_FACILITY_VERIFIED",
        "jita_material_ask_depth_verified_in_snapshot":True,
        "jita_product_buy_depth_verified_in_snapshot":True,
        "contract_id":cid,"blueprint_type_id":blueprint_type,"blueprint_kind":"BPC",
        "production_runs_assumed":1,"product_type_id":product_type,"product_units":1,
        "net_profit":99_000_000,"roi":.5,"source_location":60008494,
        "contract_price_isk":100_000_000,"product_gross_isk":240_000_000,
        "material_cost_isk":10_000_000,"manufacturing_fee_reserve_isk":2_000_000,
        "sales_tax_isk":8_000_000,
    }


def cash(cid, items):
    return {
        "kind":"contract","model_candidate":True,"status":"WATCH",
        "reason":"LIVE_ORDER_AND_CONTRACT_NOT_REVALIDATED",
        "contract_id":cid,"contract_price":100_000_000,
        "valuation_basis":MARKET_BASIS,
        "valuation_location_id":60003760,"destination_location":60003760,
        "net_profit":80_000_000,"roi":.5,"cost":110_000_000,
        "stress_profit":None,"included_items":items,
        "energy_crystal_value_share":0.0,
        "source_location":60008494,
    }


def write_run(root, proof_rows):
    folder=root/"runs"/"20261017T112301Z-filter"
    folder.mkdir(parents=True)
    (folder/"manifest.json").write_text(json.dumps({
        "status":"SHADOW_RECORDED","mail_enabled":False,"ready_for_production":False,
        "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
        "source_input_integrity":"ALL_PARSED"
    }))
    (folder/"deep_shadow.json").write_text(json.dumps({
        "status":"SHADOW_ONLY_NO_LIVE_ALERTS",
        "market_pricing_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT",
        "market_execution_basis":"OPTIMIZED_MATCHED_QUANTITY_AND_VWAP",
        "market_proofs_examined":sum(x["kind"]=="market" for x in proof_rows),
        "contract_pricing_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT",
        "contract_approved_locations_examined":sum(x["kind"]=="contract" for x in proof_rows),
        "contract_crystal_screen_basis":"JITA_BUY_DEPTH_BY_INVENTORY_GROUP",
        "contract_partial_valuation_basis":"JITA_CREDITED_REGULAR_BUY_DEPTH_IGNORED_CARGO_ZERO",
        "blueprint_manufacturing_recipe_status":"INSTALLED",
        "catalog_meta":{"sha256":"fixture-sha"}
    }))
    (folder/"all_proofs.jsonl").write_text(
        "".join(json.dumps(row)+"\n" for row in proof_rows),encoding="utf-8")
    return folder


class ShipExclusionTests(unittest.TestCase):
    def test_every_named_capital_and_freighter_ship_group(self):
        self.assertEqual(len(CAPITAL_GROUPS),8)
        self.assertEqual(len(FREIGHTER_GROUPS),2)
        blocked=build_policy(catalogue(),recipes())
        for t in range(101,111):
            self.assertTrue(blocked.blocks_market(t),t)
        self.assertFalse(blocked.blocks_market(34))
        self.assertFalse(blocked.blocks_market(111))
        self.assertEqual(len(BLOCKED_SHIP_GROUPS),10)

    def test_blueprint_output_group_and_mixed_contract_zero_value_bonus(self):
        blocked=build_policy(catalogue(),recipes())
        self.assertTrue(blocked.blocks_blueprint(201,103))
        self.assertFalse(blocked.blocks_blueprint(202,111))
        self.assertTrue(blocked.blocks_contract({"34":100,"201":1}))
        self.assertTrue(blocked.blocks_contract({"34":100,"101":1}))
        self.assertFalse(blocked.blocks_contract({"34":100,"202":1}))
        self.assertTrue(blocked.blocks_contract({"34":100,"203":1}))
        self.assertTrue(blocked.blocks_contract({}))
        self.assertTrue(blocked.blocks_market("not-a-type"))
        self.assertEqual(blocked.catalog_sha256,"fixture-sha")

    def test_real_catalog_version_fails_closed_not_untagged_mail(self):
        with tempfile.TemporaryDirectory() as td:
            repo=Path(td)
            path=repo/".cache/v4/reference/catalog.json.gz"
            catalogue().save(path)
            # Catalog SHA doesn't match archived scan = never mail arbitrary
            # old or mixed-generation classification.
            with self.assertRaisesRegex(RuntimeError,"VERSION_MISMATCH"):
                load_policy_for_run({"catalog_meta":{"sha256":"mismatch"}},repo=repo)
            self.assertIsNone(load_policy_for_run({},repo=repo))
            self.assertEqual(
                len(load_policy_for_run({"catalog_meta":{"sha256":"fixture-sha"}},
                                        repo=repo).blocked_hull_types),10)

    def test_all_three_mail_categories_filtered_before_ten_slot_cap(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            rows=(
                [market(101)] + [market(111) for _ in range(11)] +
                [cash(1001,{"34":100,"101":1})] +
                [cash(1002,{"34":100,"201":1})] +
                [cash(1003,{"34":100,"202":1})] +
                [blueprint(2001,201,103)] +
                [blueprint(2002,202,111)]
            )
            write_run(root,rows)
            policy=build_policy(catalogue(),recipes())
            with patch("v4.contract_review.load_policy_for_run",return_value=policy), \
                 patch("v4.unified_review.load_policy_for_run",return_value=policy):
                review=make_review(root)
            self.assertEqual(review["market_research_leads_total"],11)
            self.assertEqual(len(review["market_research_leads"]),10)
            self.assertEqual(review["market_research_leads"][0]["type_id"],111)
            self.assertEqual(review["contract_research_leads_total"],1)
            self.assertEqual(review["contract_research_leads"][0]["contract_id"],1003)
            self.assertEqual(review["blueprint_research_leads_total"],1)
            self.assertEqual(review["blueprint_research_leads"][0]["contract_id"],2002)
            self.assertEqual(review["excluded_capital_freighter_market_leads"],1)
            self.assertEqual(review["excluded_capital_freighter_contract_leads"],2)
            self.assertEqual(review["excluded_capital_freighter_blueprint_leads"],1)
            self.assertEqual(review["ship_exclusion_policy"],POLICY_NAME)
            subject,body=render(review)
            self.assertIn("市场10 合同1 蓝图制造1",subject)
            self.assertNotIn("合同 1001",body)
            self.assertNotIn("合同 1002",body)
            self.assertNotIn("2001",body)
            self.assertIn("1003",body)
            _,rich=render_html(review)
            self.assertNotIn("/c/1001",rich)
            self.assertNotIn("/c/1002",rich)
            self.assertNotIn("/c/2001",rich)

    def test_standalone_contract_review_also_filters_before_limit(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            folder=write_run(root,[
                cash(1001,{"34":2,"102":1}),
                cash(1002,{"34":2}),
            ])
            policy=build_policy(catalogue(),recipes())
            with patch("v4.contract_review.load_policy_for_run",return_value=policy):
                report=standalone_contract_review(root,limit=1)
            self.assertEqual(report["research_leads_total"],1)
            self.assertEqual(report["research_leads"][0]["contract_id"],1002)
            self.assertEqual(report["excluded_capital_freighter_contract_leads"],1)


if __name__=="__main__":
    unittest.main()
