"""Production contract subset: entire purchase price, only quoted goods credited."""
from __future__ import annotations

import unittest

from v4.catalog import Catalog
from v4.engine import Order, Policy, quarantine_snapshot_candidate
from v4.contract_content_policy import eligible_contract_research
from v4.contract_partial import partial_cash_contract_proof

JITA=60003760
C_J=1049588174021


def bid(t,p,q=20,minimum=1,n=1):
    return Order(order_id=t*10+n,type_id=t,location_id=JITA,buy=True,
                 price=p,remaining=q,minimum=minimum)


def ask(t,p,q=20,n=1):
    return Order(order_id=t*100+n,type_id=t,location_id=JITA,buy=False,
                 price=p,remaining=q)


class PartialContractTests(unittest.TestCase):
    def setUp(self):
        self.catalog=Catalog({
            "34":[1,"regular",18],
            "35":[1,"regular",18],
            "36":[100,"regular",18],
            "37":[1,"blueprint_type",9],
            "38":[1,"regular",86],
            "39":[1,"regular",None],
        },{"schema":2,"type_count":6})
        self.offer={"contract_id":55555,"type":"item_exchange","price":100_000_000}

    def profit(self,items,books,price=100_000_000,ask_books=None):
        return partial_cash_contract_proof(
            {**self.offer,"price":price},items,books,self.catalog,
            lambda v:10_000_000+100*v,ask_books=ask_books)

    def test_one_profitable_subset_pays_whole_bundle_ignores_bpo_and_missing_type(self):
        p=self.profit({34:2,37:1,39:100,200000:50},
                      {34:[bid(34,100_000_000,2)]})
        self.assertEqual(p["credited_items"],{"34":2})
        self.assertEqual(p["gross"],200_000_000)
        self.assertEqual(p["ignored_types_count"],3)
        self.assertEqual(p["ignored_blueprint_types"],1)
        self.assertEqual(p["ignored_unclassified_types"],2)
        self.assertEqual(p["status"],"MAIL")
        self.assertAlmostEqual(p["net_profit"],83_249_800)
        self.assertGreater(p["roi"],.1)
        self.assertIsNone(p["stress_profit"])

    def test_partial_bid_depth_no_longer_drops_other_99_units(self):
        p=self.profit({34:100},{34:[bid(34,150_000_000,1)]})
        self.assertEqual(p["credited_items"],{"34":100})
        self.assertEqual(p["gross"],15_000_000_000)
        self.assertEqual(p["status"],"MAIL")
        self.assertEqual(p["ordinary_price_sources"]["34"],
                         "JITA_TOP5_BUY_LEVEL_MEAN_NOT_EXECUTABLE")
        self.assertIn("JITA_BUY_DEPTH_INSUFFICIENT",
                      p["contract_liquidity_risk_flags"])
        self.assertFalse(p["jita_buy_depth_sufficient_for_credited_items"])
        self.assertEqual(p["matched_jita_buy_units"],1)
        self.assertEqual(p["credited_jita_buy_order_ids"],[])

    def test_no_buy_orders_uses_jita_ask_reference_without_claiming_sale(self):
        p=self.profit({34:2,37:1},{},ask_books={
            34:[ask(34,130_000_000,n=1),
                ask(34,150_000_000,n=2)]})
        self.assertEqual(p["credited_items"],{"34":2})
        self.assertEqual(p["ignored_blueprint_types"],1)
        self.assertEqual(p["gross"],280_000_000)
        self.assertEqual(p["status"],"MAIL")
        self.assertEqual(p["ordinary_price_sources"]["34"],
                         "JITA_TOP5_ASK_ONLY_UPPER_BOUND_NO_BUY_ORDERS")
        self.assertEqual(p["contract_ask_only_reference_share"],1.0)
        self.assertIn("ASK_PRICE_IS_NOT_A_SELL_EXIT_PRICE",
                      p["contract_liquidity_risk_flags"])
        self.assertFalse(p["jita_buy_depth_sufficient_for_credited_items"])
        quarantine_snapshot_candidate(p)
        self.assertFalse(p.get("actionable",False))
        self.assertEqual(p["status"],"WATCH")

    def test_no_bid_or_ask_has_no_invented_price(self):
        p=self.profit({34:2},{})
        self.assertEqual(p["status"],"WATCH")
        self.assertEqual(p["reason"],
                         "NO_JITA_REFERENCE_PRICE_FOR_REGULAR_SUBSET")
        self.assertEqual(p["ignored_no_reference_types"],1)
        self.assertEqual(p["credited_type_candidates"],0)

    def test_full_bid_liquidity_still_uses_real_matched_depth(self):
        p=self.profit({34:2},{34:[
            bid(34,140_000_000,1,n=1),
            bid(34,120_000_000,1,n=2)]})
        self.assertEqual(p["gross"],260_000_000)
        self.assertTrue(p["jita_buy_depth_sufficient_for_credited_items"])
        self.assertEqual(p["contract_liquidity_risk_flags"],[])
        self.assertEqual(p["ordinary_price_sources"]["34"],
                         "JITA_BUY_DEPTH_FULL_SNAPSHOT")

    def test_laser_dominated_credited_value_never_alerted(self):
        p=self.profit({38:2,37:1},{38:[bid(38,100_000_000,2)]})
        self.assertEqual(p["energy_crystal_value_share"],1)
        self.assertEqual(p["status"],"WATCH")

    def test_unknown_laser_class_cannot_be_credited(self):
        p=self.profit({39:1},{39:[bid(39,1_000_000_000,1)]})
        self.assertEqual(p["status"],"WATCH")
        self.assertEqual(p["reason"],"NO_JITA_REFERENCE_PRICE_FOR_REGULAR_SUBSET")
        self.assertEqual(p["ignored_unclassified_types"],1)

    def test_roi_strictly_above_ten_percent_and_stress_advisory(self):
        self.assertTrue(eligible_contract_research(
            net_profit=60_000_000,roi=.1001,stress=None,cost=300_000_000,
            crystal_share=0,category_required=True,partial_mode=True))
        self.assertFalse(eligible_contract_research(
            net_profit=60_000_000,roi=.10,stress=None,cost=300_000_000,
            crystal_share=0,category_required=True,partial_mode=True))
        self.assertFalse(eligible_contract_research(
            net_profit=60_000_000,roi=.1001,stress=None,cost=300_000_000,
            crystal_share=0,category_required=True))

    def test_snapshot_is_not_formal_mail(self):
        p=self.profit({34:2},{34:[bid(34,200_000_000,2)]})
        quarantine_snapshot_candidate(p)
        self.assertEqual(p["status"],"WATCH")
        self.assertTrue(p["model_candidate"])


if __name__=="__main__":
    unittest.main()
