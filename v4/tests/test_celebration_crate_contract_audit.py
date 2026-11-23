"""Offline deterministic contract-funnel regression tests (no network/side effects)."""
import unittest
from datetime import datetime, timezone

from v4.celebration_crate_contract_audit import audit_rows, JITA, GLOBAL_PLEX_REGION


class Catalog:
    def volume(self,t):
        return 2 if t == 80240 else 1
    def classification(self,t):
        return "regular"


class ContractFunnelTests(unittest.TestCase):
    def setUp(self):
        self.at=datetime(2026,11,23,2,29,tzinfo=timezone.utc)
        self.catalog=Catalog()
        self.market=[
            dict(order_id=1,type_id=44992,region_id=GLOBAL_PLEX_REGION,
                 location_id=JITA,price=4_878_000,volume_remain=10_000,
                 min_volume=1,is_buy_order=True),
            dict(order_id=2,type_id=44992,region_id=GLOBAL_PLEX_REGION,
                 location_id=60008494,price=4_879_000,volume_remain=100,
                 min_volume=1,is_buy_order=True),
            dict(order_id=3,type_id=34,region_id=10000002,
                 location_id=JITA,price=1_000_000,volume_remain=3,
                 min_volume=1,is_buy_order=True),
        ]
        self.contracts=[
            dict(contract_id=10,start_location_id=JITA,type="item_exchange",
                 status="outstanding",price=80_000_000),
            dict(contract_id=11,start_location_id=JITA,type="item_exchange",
                 status="outstanding",price=110_000_000),
            dict(contract_id=12,start_location_id=JITA,type="item_exchange",
                 status="outstanding",price=1),
            dict(contract_id=13,start_location_id=JITA,type="item_exchange",
                 status="outstanding",price=1,date_expired=float("nan")),
        ]
        self.items=[
            dict(contract_id=cid,type_id=80240,quantity=1,is_included=True)
            for cid in (10,11,12,13)
        ] + [dict(contract_id=12,type_id=34,quantity=1,is_included=False)]
        self.haul=lambda loc,volume:0

    def audit(self):
        return audit_rows(self.contracts,self.items,self.market,
                          locations={JITA},catalog=self.catalog,
                          haul_fn=self.haul,at=self.at)

    def test_contracts_all_classified(self):
        a=self.audit()
        self.assertEqual(a["contracts_with_included_target_crate_in_locations"],4)
        self.assertEqual(a["reason_counts"]["POSITIVE_JITA_RESEARCH_ESTIMATE_CHECK_SCANNER_FILTER"],1)
        self.assertEqual(a["reason_counts"]["LOSS_EVEN_BEFORE_HAUL"],1)
        self.assertEqual(a["reason_counts"]["CONTRACT_REQUESTS_ITEMS"],1)
        self.assertEqual(a["reason_counts"]["UNPARSEABLE_EXPIRY_SCANNER_REJECTS"],1)

    def test_global_npc_price_only_counterfactual(self):
        a=self.audit()
        p=next(x for x in a["contracts"] if x["contract_id"]==10)
        self.assertEqual(p["guaranteed_plex"],20)
        self.assertAlmostEqual(p["gross_jita_isk"],97_560_000)
        self.assertGreater(p["net_before_haul_global_npc_isk"],
                           p["net_before_haul_jita_isk"])
        self.assertAlmostEqual(p["global_npc_vs_jita_gain_before_haul_isk"],
                               20_000*(1-0.03375))
        self.assertEqual(p["net_after_haul_jita_isk"],p["net_before_haul_jita_isk"])

    def test_partial_other_jita_buy_depth_and_contract_price_once(self):
        self.contracts=[dict(contract_id=10,start_location_id=JITA,
                             type="item_exchange",status="outstanding",
                             price=80_000_000)]
        self.items=[dict(contract_id=10,type_id=80240,
                         quantity=1,is_included=True),
                    dict(contract_id=10,type_id=34,
                         quantity=30,is_included=True)]
        a=self.audit()
        p=a["contracts"][0]
        self.assertAlmostEqual(p["gross_jita_isk"],100_560_000)
        self.assertEqual(p["other_items_jita_matched"][0]["matched"],3)
        self.assertEqual(p["other_items_jita_matched"][0]["requested"],30)
        self.assertAlmostEqual(p["net_before_haul_jita_isk"],
                               100_560_000*(1-0.03375)-80_000_000)


if __name__=="__main__":
    unittest.main()
