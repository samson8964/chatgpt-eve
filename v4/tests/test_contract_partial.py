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

    def profit(self,items,books,price=100_000_000):
        return partial_cash_contract_proof(
            {**self.offer,"price":price},items,books,self.catalog,
            lambda v:10_000_000+100*v)

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

    def test_partial_bid_depth_recovers_purchase_without_full_liquidation(self):
        p=self.profit({34:100},{34:[bid(34,150_000_000,1)]})
        self.assertEqual(p["credited_items"],{"34":1})
        self.assertEqual(p["status"],"WATCH") # 150m gross -100m -10m transport - 3.375% tax <50m
        p=self.profit({34:100},{34:[bid(34,230_000_000,1)]})
        self.assertEqual(p["credited_items"],{"34":1})
        self.assertEqual(p["status"],"MAIL")

    def test_laser_dominated_credited_value_never_alerted(self):
        p=self.profit({38:2,37:1},{38:[bid(38,100_000_000,2)]})
        self.assertEqual(p["energy_crystal_value_share"],1)
        self.assertEqual(p["status"],"WATCH")

    def test_unknown_laser_class_cannot_be_credited(self):
        p=self.profit({39:1},{39:[bid(39,1_000_000_000,1)]})
        self.assertEqual(p["status"],"WATCH")
        self.assertEqual(p["reason"],"NO_JITA_BUY_LIQUIDITY_FOR_REGULAR_SUBSET")
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
