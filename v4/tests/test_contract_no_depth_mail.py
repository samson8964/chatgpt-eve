"""Integration: no Jita BUY orders can still enter ordinary contract RESEARCH mail."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v4.catalog import Catalog
from v4.engine import Order, quarantine_snapshot_candidate
from v4.contract_partial import (
    partial_cash_contract_proof, CONTRACT_REFERENCE_BASIS, CONTRACT_VALUATION_BASIS,
)
from v4.contract_review import make_review as contract_review
from v4.unified_review import make_review as unified_review, render, render_html

JITA = 60003760
NEW_BASIS = "JITA_4_4_REGULAR_REFERENCE_NO_BUY_DEPTH_GATE"


class ContractNoDepthMailTests(unittest.TestCase):
    def test_ask_only_contract_and_bpc_are_separate_mail_research_lanes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            run=root/"runs"/"20261110T122301Z-test"
            run.mkdir(parents=True)
            offer={"contract_id":7345,"type":"item_exchange","price":100_000_000}
            included={34:2, 37:1}  # BPO ignored in BOTH cash and manufacturing profit
            catalog=Catalog({"34":[1,"regular",18],"37":[.01,"blueprint_type",9]},
                            {"type_count":2,"schema":2})
            ask=[Order(order_id=991,type_id=34,location_id=JITA,buy=False,
                       price=140_000_000,remaining=1),
                 Order(order_id=992,type_id=34,location_id=JITA,buy=False,
                       price=160_000_000,remaining=1)]
            proof=partial_cash_contract_proof(
                offer,included,{},catalog,lambda volume: 1_000_000,
                ask_books={34:ask})
            self.assertTrue(proof["policy_passed"])
            self.assertEqual(proof["ordinary_price_sources"]["34"],
                             "JITA_TOP5_ASK_ONLY_UPPER_BOUND_NO_BUY_ORDERS")
            self.assertEqual(proof["credited_items"],{"34":2})
            proof.update(included_items={"34":2,"37":1},
                contract_price=100_000_000,valuation_basis=CONTRACT_VALUATION_BASIS,
                valuation_location_id=JITA,destination_location=JITA,
                source_location=JITA,contract_access_verified=False,
                requested_items_present=False)
            quarantine_snapshot_candidate(proof)
            self.assertEqual(proof["status"],"WATCH")
            self.assertTrue(proof["model_candidate"])

            # Minimal separately modelled BPC proof under the SAME contract_id.
            bp={
                "kind":"blueprint_manufacturing","status":"WATCH",
                "reason":"BLUEPRINT_BPC_TOP5_30PCT_ESI_FEE_RESEARCH_ONLY",
                "model_candidate":True,"contract_id":7345,
                "blueprint_kind":"BPC","blueprint_type_id":38,
                "product_type_id":39,"production_runs_assumed":5,
                "product_units":5,"bundle_blueprint_total":1,
                "bundle_blueprint_selected":1,
                "bundle_selected_details":[{"blueprint_type_id":38,
                                            "product_type_id":39}],
                "valuation_basis":"JITA_TOP5_BPC_MANUFACTURE_30PCT_BUNDLE_ESTIMATE",
                "facility_fee_status":"ESI_ADJUSTED_PRICES_SYSTEM_COST_INDEX_JITA_NPC_REFERENCE_NOT_JOB_QUOTE",
                "manufacturing_fee_snapshot_verified":True,
                "jita_material_top5_prices_observed":True,
                "jita_product_top5_prices_observed":True,
                "net_profit":150_000_000,"roi":.4,"risk_score":25,
                "manufacturing_fee_isk":1_000_000,
                "contract_price_isk":100_000_000,"material_cost_isk":2_000_000,
                "source_location":JITA,
            }
            (run/"manifest.json").write_text(json.dumps({
                "status":"SHADOW_RECORDED","mail_enabled":False,
                "ready_for_production":False,
                "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
                "source_input_integrity":"ALL_PARSED"}),encoding="utf-8")
            (run/"deep_shadow.json").write_text(json.dumps({
                "status":"SHADOW_ONLY_NO_LIVE_ALERTS",
                "market_pricing_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT",
                "market_execution_basis":"OPTIMIZED_MATCHED_QUANTITY_AND_VWAP",
                "market_proofs_examined":0,
                "contract_approved_locations_examined":1,
                "contract_pricing_basis":NEW_BASIS,
                "contract_partial_valuation_basis":CONTRACT_REFERENCE_BASIS,
            }),encoding="utf-8")
            (run/"all_proofs.jsonl").write_text(
                "".join(json.dumps(x)+"\n" for x in (proof,bp)),encoding="utf-8")
            with patch("v4.contract_review.load_policy_for_run",return_value=None), \
                 patch("v4.unified_review.load_policy_for_run",return_value=None):
                contract=contract_review(root)
                unified=unified_review(root)
            self.assertEqual(contract["research_leads_total"],1)
            self.assertEqual(unified["contract_research_leads_total"],1)
            self.assertEqual(unified["blueprint_research_leads_total"],1)
            self.assertEqual(unified["contract_research_leads"][0]["contract_id"],7345)
            self.assertEqual(unified["blueprint_research_leads"][0]["contract_id"],7345)
            self.assertEqual(unified["contract_research_leads"][0]
                             ["contract_ask_only_reference_share"],1.0)
            subject,plain=render(unified)
            self.assertIn("合同1 蓝图制造1",subject)
            self.assertIn("卖价上界",plain)
            self.assertIn("不代表可成交收入",plain)
            _,rich=render_html(unified)
            self.assertIn("卖价上界",rich)
            self.assertIn("不代表可成交收入",rich)


if __name__=="__main__":
    unittest.main()
