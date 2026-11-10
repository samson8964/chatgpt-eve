"""Approved BPC pricing, bundle and risk-ranking regression tests."""
from __future__ import annotations

import unittest

from v4.engine import Order
from v4.blueprint_manufacturing import (
    evaluate_one, evaluate_blueprint_contract, top_five_levels,
)
from v4.unified_review import research_mail_eligible, research_profit_sort_key
from v4.tests.test_industry_fees import context

JITA = 60003760


def levels(typ, prices, buy, *, quantity=1):
    return [Order(order_id=typ*100+i, type_id=typ, location_id=JITA,
                  buy=buy, price=p, remaining=quantity)
            for i,p in enumerate(prices)]


class BpcStrategyTests(unittest.TestCase):
    def setUp(self):
        self.contract={"contract_id":123,"price":50_000_000,
                       "start_location_id":JITA}
        self.blueprints=[{"type_id":100+i,"quantity":1,"runs":20,
                          "is_blueprint_copy":True,"material_efficiency":10}
                         for i in range(4)]
        self.recipes={str(100+i):{"materials":{"34":10},
                                 "products":{str(200+i):1},
                                 "time_seconds":60} for i in range(4)}
        self.books={(JITA,34,False):levels(34,[9,10,11,12,13,14],False)}
        for i in range(4):
            self.books[(JITA,200+i,True)]=levels(
                200+i,[1_000_000+(3-i)*100_000,800_000,700_000,
                       600_000,500_000,400_000],True)

    def test_five_distinct_price_levels_not_volume_weighted(self):
        asks=levels(34,[10,10,20,30,40,50,60],False,quantity=1)
        q=top_five_levels(asks,buy=False)
        self.assertEqual(q["levels"],[10,20,30,40,50])
        self.assertEqual(q["unit_price"],30)
        self.assertEqual(q["price_levels"],5)
        bid=top_five_levels(levels(35,[100,90,80,70,60,50],True),buy=True)
        self.assertEqual(bid["unit_price"],80)

    def test_material_price_does_not_require_20_runs_depth(self):
        bp=self.blueprints[0]
        r=evaluate_one(self.contract,bp,self.recipes["100"],
                       {34:levels(34,[9,10,11,12,13],False)},
                       {200:levels(200,[1_000_000,900_000,800_000,700_000,600_000],True)},
                       0,fee_context=context(adjusted_prices={34:10}))
        self.assertIsNotNone(r)
        self.assertEqual(r["production_runs_assumed"],20)
        self.assertEqual(r["product_unit_price_estimate_isk"],800_000)
        self.assertEqual(r["material_cost_isk"],180*11)
        self.assertIn("SNAPSHOT_DEPTH_BELOW_MODEL_QUANTITY",r["risk_flags"])

    def test_bundle_top_30_percent_ceil_and_full_contract_once(self):
        proof=evaluate_blueprint_contract(
            self.contract,self.blueprints,self.recipes,self.books,0,
            fee_context=context(adjusted_prices={34:10}))
        self.assertIsNotNone(proof)
        self.assertEqual(proof["bundle_blueprint_total"],4)
        self.assertEqual(proof["bundle_blueprint_selected"],2)
        self.assertEqual(proof["bundle_selected_type_ids"],[100,101])
        self.assertEqual(proof["contract_price_isk"],50_000_000)
        self.assertEqual(proof["production_runs_assumed"],20)
        self.assertEqual(proof["valuation_basis"],
                         "JITA_TOP5_BPC_MANUFACTURE_30PCT_BUNDLE_ESTIMATE")
        self.assertEqual(proof["status"],"WATCH")
        self.assertFalse(proof["actionable"])
        self.assertAlmostEqual(proof["net_profit"],
            proof["manufacturing_contribution_isk"]-50_000_000)

    def test_mixed_bpo_contract_keeps_other_bpc_value(self):
        bp={**self.blueprints[0],"is_blueprint_copy":False,"runs":-1}
        result=evaluate_blueprint_contract(
            self.contract,[bp,self.blueprints[1]],self.recipes,
            self.books,0,fee_context=context(adjusted_prices={34:10}))
        self.assertIsNotNone(result)
        self.assertEqual(result["bundle_blueprint_total"],1)
        self.assertEqual(result["bundle_blueprint_ignored_bpo"],1)
        self.assertEqual(result["bundle_selected_type_ids"],[101])
        self.assertEqual(result["contract_price_isk"],50_000_000)
        # The BPO is ignored, not a reason to lose the BPC research proof.

    def test_bundle_missing_bpc_does_not_invent_value(self):
        proof=evaluate_blueprint_contract(
            self.contract,self.blueprints,self.recipes,
            {**self.books,(JITA,203,True):[]},0,
            fee_context=context(adjusted_prices={34:10}))
        self.assertEqual(proof["bundle_blueprint_total"],4)
        self.assertEqual(proof["bundle_blueprint_evaluated"],3)
        self.assertIn("BPC_VALUE_MISSING_IN_BUNDLE",proof["risk_flags"])

    def test_mail_gates_and_profit_first_sort_not_risk_weighted(self):
        below=dict(net_profit_snapshot=49_999_999,roi_snapshot=.8,risk_score=0,
                   contract_id=1)
        low_roi=dict(net_profit_snapshot=500_000_000,roi_snapshot=.1,
                     risk_score=0,contract_id=2)
        a=dict(net_profit_snapshot=500_000_000,roi_snapshot=.11,risk_score=100,
               contract_id=3)
        b=dict(net_profit_snapshot=100_000_000,roi_snapshot=2.,risk_score=0,
               contract_id=4)
        self.assertFalse(research_mail_eligible(below))
        self.assertFalse(research_mail_eligible(low_roi))
        self.assertTrue(research_mail_eligible(a))
        self.assertTrue(research_mail_eligible(b))
        self.assertEqual(sorted([b,a],key=research_profit_sort_key)[0]["contract_id"],3)


if __name__ == "__main__":
    unittest.main()
