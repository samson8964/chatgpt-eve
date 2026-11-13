"""ESI-based manufacturing fee unit tests: offline, deterministic, no market calls."""
from __future__ import annotations

import math
import unittest

from v4.engine import Order
from v4.industry_fees import (
    ManufacturingFeeContext, load_jita_npc_fee_context, FEE_BASIS,
    JITA_NPC_STATION_ID, JITA_SOLAR_SYSTEM_ID,
)
from v4.blueprint_manufacturing import evaluate_one, evaluate_blueprint_contract


def context(**kwargs):
    options = dict(
        system_id=JITA_SOLAR_SYSTEM_ID,
        facility_id=JITA_NPC_STATION_ID,
        manufacturing_cost_index=0.10,
        adjusted_prices={34: 100_000.0, 35: 1_000_000.0},
        observed_at_utc="2026-11-10T00:00:00+00:00",
    )
    options.update(kwargs)
    return ManufacturingFeeContext(**options)


def book(typ, price, buy):
    return [Order(order_id=typ*10+int(buy), type_id=typ,
                  location_id=JITA_NPC_STATION_ID,
                  buy=buy, price=price, remaining=10000)]


class ManufacturingFeeTests(unittest.TestCase):
    def setUp(self):
        self.recipe = {"materials": {"34":100, "35":1},
                       "products": {"36":2}, "time_seconds":600}
        self.contract = {"contract_id":314, "price":200_000_000,
                         "start_location_id":JITA_NPC_STATION_ID}
        self.blueprint = {"type_id":101, "quantity":1,
                          "is_blueprint_copy":True, "runs":2,
                          "material_efficiency":10}
        self.asks = {34:book(34, 100_000, False),
                     35:book(35, 1_000_000, False)}
        self.bids = {36:book(36, 200_000_000, True)}

    def test_eiv_does_not_use_me_reduced_materials(self):
        fee = context().quote(self.recipe, 2)
        self.assertEqual(fee["manufacturing_eiv_isk"], 22_000_000)
        self.assertEqual(fee["manufacturing_fee_index_isk"], 2_200_000)
        self.assertEqual(fee["manufacturing_fee_facility_tax_isk"], 55_000)
        self.assertEqual(fee["manufacturing_fee_scc_isk"], 880_000)
        self.assertEqual(fee["manufacturing_fee_isk"], 3_135_000)
        self.assertFalse(fee["manufacturing_job_quote_verified"])

    def test_facility_modifier_and_alpha_are_explicit(self):
        fee = context(system_index_multiplier=.95,
                      alpha_tax_rate=.0025).quote(self.recipe, 2)
        self.assertEqual(fee["manufacturing_fee_index_isk"], 2_090_000)
        self.assertEqual(fee["manufacturing_fee_alpha_tax_isk"], 55_000)
        self.assertEqual(fee["manufacturing_fee_isk"], 3_080_000)

    def test_missing_adjusted_price_fails_closed(self):
        self.assertIsNone(context(adjusted_prices={34:100}).quote(self.recipe, 2))
        self.assertIsNone(context(adjusted_prices={34:math.nan,35:1})
                          .quote(self.recipe, 2))
        self.assertIsNone(context().quote(self.recipe, 0))

    def test_invalid_rate_rejected(self):
        with self.assertRaises(ValueError):
            context(manufacturing_cost_index=-.01)
        with self.assertRaises(ValueError):
            context(system_index_multiplier=0)

    def test_loader_uses_two_public_endpoints_not_estimated_prices(self):
        paths = []
        def fetch(url):
            paths.append(url)
            if url.endswith("/industry/systems/"):
                return ([{"solar_system_id":30000142,
                          "cost_indices":[{"activity":"manufacturing",
                                           "cost_index":.125}]}], {})
            if url.endswith("/markets/prices/"):
                return ([{"type_id":34, "average_price":120,
                          "adjusted_price":100},
                         {"type_id":35, "adjusted_price":200}], {})
            raise AssertionError(url)
        fee = load_jita_npc_fee_context(fetch=fetch)
        self.assertEqual(len(paths),2)
        self.assertEqual(fee.manufacturing_cost_index,.125)
        self.assertEqual(fee.adjusted_prices[34],100)

    def test_loader_fails_when_system_missing(self):
        def fetch(url):
            if url.endswith("/industry/systems/"):
                return []
            return [{"type_id":34,"adjusted_price":100}]
        with self.assertRaisesRegex(ValueError,"JITA_MANUFACTURING_SYSTEM_INDEX_MISSING"):
            load_jita_npc_fee_context(fetch=fetch)

    def test_existing_blueprint_evaluation_uses_new_fee(self):
        result=evaluate_one(self.contract,self.blueprint,self.recipe,
                            self.asks,self.bids,3_000_000,fee_context=context())
        self.assertIsNotNone(result)
        self.assertEqual(result["required_materials"],{"34":180,"35":2})
        self.assertEqual(result["material_cost_isk"],20_000_000)
        self.assertEqual(result["manufacturing_fee_isk"],3_135_000)
        self.assertEqual(result["manufacturing_contribution_isk"],749_865_000)
        self.assertEqual(result["facility_fee_status"],FEE_BASIS)
        self.assertTrue(result["manufacturing_fee_snapshot_verified"])
        self.assertFalse(result["live_verified"])
        self.assertFalse(result["actionable"])

    def test_unpriceable_fee_never_fabricates_blueprint_profit(self):
        result=evaluate_one(self.contract,self.blueprint,self.recipe,
                            self.asks,self.bids,0,
                            fee_context=context(adjusted_prices={34:100}))
        self.assertIsNone(result)

    def test_research_status_remains_watch(self):
        markets={
            (JITA_NPC_STATION_ID,34,False):self.asks[34],
            (JITA_NPC_STATION_ID,35,False):self.asks[35],
            (JITA_NPC_STATION_ID,36,True):self.bids[36],
        }
        proof=evaluate_blueprint_contract(self.contract,[self.blueprint],
            {"101":self.recipe},markets,3_000_000,
            fee_context=context())
        self.assertEqual(proof["status"],"WATCH")
        self.assertEqual(proof["reason"],
             "BLUEPRINT_BPC_TOP5_30PCT_ESI_FEE_RESEARCH_ONLY")
        self.assertTrue(proof["model_candidate"])
        self.assertEqual(proof["facility_fee_status"],FEE_BASIS)


if __name__=="__main__":
    unittest.main()
