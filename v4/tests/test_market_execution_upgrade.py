"""Focused non-A/B correctness tests for approved V4 depth/VWAP replacement."""
from __future__ import annotations

import math
import unittest

from v4.engine import Order, Policy, market_proof
from v4.market_execution import (gross_depth_upper_bound,
                                 profitable_breakpoints, candidate_quantities)
from v4.market_depth import station_sell_census

JITA = 60003760
SOURCE = 1053970513596


def order(ident, price, volume, *, buy=False, where=None, minimum=1):
    return Order(ident, 41058, JITA if buy else SOURCE, buy,
                 price, volume, minimum=minimum)


class ApprovedDepthAlgorithmTests(unittest.TestCase):
    def test_gross_upper_bound_uses_real_both_side_depth(self):
        asks=[order(1, 100, 10000)]
        bids=[order(2, 200, 1, buy=True)]
        self.assertEqual(gross_depth_upper_bound(asks, bids), 100)
        self.assertEqual(gross_depth_upper_bound(asks, []), 0)
        books={(SOURCE,41058,False):asks,(JITA,41058,True):bids}
        census=station_sell_census(
            books,locations={"4-H":SOURCE},floor=50_000_000)
        self.assertEqual(census["4-H"]["sell_types_with_jita_buy"],1)
        self.assertEqual(census["4-H"]["sell_types_optimistic_gate_passed"],0)
        self.assertEqual(census["4-H"]["optimistic_gate_definition"],
                         "TWO_SIDED_MATCHED_DEPTH_GROSS_MARGIN_BEFORE_FEES")

    def test_levels_are_matched_in_price_order_not_order_count(self):
        asks=[order(1,10,3), order(2,15,7)]
        bids=[order(3,30,5,buy=True), order(4,20,2,buy=True)]
        # 3 x (30-10), 2 x (30-15), 2 x (20-15)
        self.assertEqual(gross_depth_upper_bound(asks,bids),100)
        self.assertEqual(profitable_breakpoints(asks,bids,0),[3,5,7])

    def test_optimize_quantity_for_policy_and_same_lot_stress(self):
        asks=[order(1,10,10),order(2,80,10)]
        bids=[order(3,100,10,buy=True),order(4,80.5,10,buy=True)]
        policy=Policy(profit_floor=100, min_roi=2, min_density=1, sales_tax=0)
        proof=market_proof(
            asks,bids,source_location=SOURCE,destination_location=JITA,
            type_id=41058,volume_m3=1,haul_isk=None,
            haul_for_units=lambda n:0,policy=policy,allowed=True,fresh=True)
        self.assertEqual(proof["status"],"MAIL")
        self.assertEqual(proof["quantity"],10)
        self.assertAlmostEqual(proof["profit"],900)
        self.assertEqual(proof["source_vwap_isk_per_unit"],10)
        self.assertEqual(proof["jita_vwap_isk_per_unit"],100)
        self.assertAlmostEqual(proof["source_vwap_isk_per_unit"]*proof["quantity"],
                               proof["executed_sell_cost"])
        self.assertAlmostEqual(proof["jita_vwap_isk_per_unit"]*proof["quantity"],
                               proof["executed_jita_buy_gross"])
        self.assertGreater(proof["stress_profit"],0)
        self.assertTrue(proof["quantity_optimized"])

    def test_haul_is_recalculated_for_selected_units(self):
        asks=[order(1,10,10),order(2,60,10)]
        bids=[order(3,100,10,buy=True),order(4,80,10,buy=True)]
        policy=Policy(profit_floor=100,min_roi=1.5,min_density=1,sales_tax=0)
        charged=[]
        def haul(n):
            charged.append(n)
            return 10+2*n
        proof=market_proof(
            asks,bids,source_location=SOURCE,destination_location=JITA,
            type_id=41058,volume_m3=2,haul_isk=None,
            haul_for_units=haul,policy=policy,allowed=True,fresh=True)
        self.assertEqual(proof["quantity"],10)
        self.assertEqual(proof["haul"],30)
        self.assertIn(10,charged)
        self.assertAlmostEqual(proof["profit"],870)

    def test_stress_must_cover_same_units_not_smaller_fallback(self):
        asks=[order(1,10,10),order(2,11,4)]
        bids=[order(3,100,10,buy=True),order(4,90,4,buy=True)]
        policy=Policy(profit_floor=100,min_roi=.1,min_density=1,sales_tax=0)
        proof=market_proof(
            asks,bids,source_location=SOURCE,destination_location=JITA,
            type_id=41058,volume_m3=1,haul_isk=0,policy=policy,
            allowed=True,fresh=True)
        # The 10-unit plan is NOT stress-safe, but the smaller 4-unit lot
        # is independently executable AND stress-safe: choose it directly.
        self.assertEqual(proof["status"],"MAIL")
        self.assertEqual(proof["quantity"],4)
        self.assertEqual(proof["matched_depth_units"],4)
        self.assertGreater(proof["stress_profit"],0)

    def test_single_discount_ask_survives_buy_only_stress(self):
        # Removing the only cheap source ask would reject a genuine purchase
        # opportunity even though replacement Jita BUY depth is sufficient.
        asks=[order(1, 10_000_000, 1)]
        bids=[order(2, 100_000_000, 1, buy=True),
              order(3, 85_000_000, 1, buy=True)]
        policy=Policy(sales_tax=0)
        proof=market_proof(
            asks,bids,source_location=SOURCE,destination_location=JITA,
            type_id=41058,volume_m3=1,haul_isk=0,policy=policy,
            allowed=True,fresh=True)
        self.assertEqual(proof["status"],"MAIL")
        self.assertEqual(proof["quantity"],1)
        self.assertEqual(proof["profit"],90_000_000)
        self.assertEqual(proof["stress_profit"],75_000_000)

    def test_buy_stress_must_strictly_exceed_fifty_million(self):
        asks=[order(1,10_000_000,1)]
        bids=[order(2,100_000_000,1,buy=True),
              order(3,60_000_000,1,buy=True)]
        policy=Policy(sales_tax=0)
        proof=market_proof(
            asks,bids,source_location=SOURCE,destination_location=JITA,
            type_id=41058,volume_m3=1,haul_isk=0,policy=policy,
            allowed=True,fresh=True)
        self.assertEqual(proof["profit"],90_000_000)
        self.assertEqual(proof["stress_profit"],50_000_000)
        self.assertEqual(proof["status"],"WATCH")
        self.assertEqual(proof["reason"],"BELOW_GATE_OR_STRESS")
        bids[1]=order(3,60_000_001,1,buy=True)
        passed=market_proof(
            asks,bids,source_location=SOURCE,destination_location=JITA,
            type_id=41058,volume_m3=1,haul_isk=0,policy=policy,
            allowed=True,fresh=True)
        self.assertEqual(passed["status"],"MAIL")
        self.assertEqual(passed["stress_profit"],50_000_001)

    def test_limited_fallback_buy_depth_selects_smaller_lot(self):
        asks=[order(1,10_000_000,10)]
        bids=[order(2,110_000_000,10,buy=True),
              order(3,80_000_000,3,buy=True)]
        policy=Policy(sales_tax=0)
        self.assertIn(3,candidate_quantities(asks,bids,0))
        proof=market_proof(
            asks,bids,source_location=SOURCE,destination_location=JITA,
            type_id=41058,volume_m3=1,haul_isk=0,policy=policy,
            allowed=True,fresh=True)
        self.assertEqual(proof["status"],"MAIL")
        self.assertEqual(proof["quantity"],3)
        self.assertEqual(proof["stress_profit"],210_000_000)

    def test_unverified_freight_never_creates_optimistic_mail(self):
        asks=[order(1,10,10),order(2,11,10)]
        bids=[order(3,100,10,buy=True),order(4,99,10,buy=True)]
        proof=market_proof(
            asks,bids,source_location=SOURCE,destination_location=JITA,
            type_id=41058,volume_m3=1,haul_isk=None,
            haul_for_units=lambda n:None,allowed=True,fresh=True)
        self.assertEqual(proof["status"],"RESEARCH")
        self.assertEqual(proof["reason"],"HAUL_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
