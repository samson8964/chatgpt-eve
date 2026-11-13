"""Contract mail policy regression: energy laser crystal majority and net profit."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v4.contract_content_policy import (
    CONTRACT_MIN_NET_ISK, CRYSTAL_SHARE_BASIS,
    energy_crystal_value_share, eligible_contract_research
)
from v4.engine import Order
from v4.catalog import Catalog
from v4.contract_review import make_review

JITA=60003760


def buy(tid,price,qty=100):
    return [Order(order_id=100000+tid,type_id=tid,location_id=JITA,
                  buy=True,price=price,remaining=qty)]


class CrystalContentPolicyTests(unittest.TestCase):
    def setUp(self):
        self.catalog=Catalog({
            "34":[.01,"regular",18],
            "21194":[1,"regular",86],
            "12824":[1,"regular",374],
            "12820":[1,"regular",375],
            "2000":[1,"regular",86],
            "5000":[1,"regular",482],  # mining crystal is NOT a laser crystal
        },{"schema":2,"type_count":6})

    def test_pure_laser_crystals_and_t2_variants_are_blocked(self):
        for tid in (21194,12824,12820):
            self.assertEqual(energy_crystal_value_share(
                {tid:10},{tid:buy(tid,1_000_000)},self.catalog),1.0)

    def test_weight_by_jita_exit_value_not_units_or_volume(self):
        books={34:buy(34,100_000_000),21194:buy(21194,500_000)}
        share=energy_crystal_value_share(
            {21194:100,34:1},books,self.catalog)
        self.assertAlmostEqual(share,1/3)
        self.assertTrue(eligible_contract_research(
            net_profit=50_000_000,roi=.15,stress=5_000_000,cost=10_000_000,
            crystal_share=share,category_required=True))
        half=energy_crystal_value_share(
            {21194:100,34:1},
            {34:buy(34,50_000_000),21194:buy(21194,500_000)},self.catalog)
        self.assertEqual(half,.5)
        self.assertFalse(eligible_contract_research(
            net_profit=50_000_000,roi=.15,stress=5_000_000,cost=10_000_000,
            crystal_share=half,category_required=True))

    def test_mining_crystal_not_energy_laser_crystal(self):
        self.assertEqual(energy_crystal_value_share(
            {5000:10},{5000:buy(5000,1_000_000)},self.catalog),0)

    def test_unverifiable_group_or_depth_fails_closed(self):
        unknown=Catalog({"5555":[1,"regular",None]},{"schema":2,"type_count":1})
        self.assertIsNone(energy_crystal_value_share(
            {5555:1},{5555:buy(5555,1)},unknown))
        self.assertIsNone(energy_crystal_value_share(
            {34:1000},{34:buy(34,100)},self.catalog))
        self.assertFalse(eligible_contract_research(
            net_profit=60_000_000,roi=.2,stress=30_000_000,cost=70_000_000,
            crystal_share=None,category_required=True))

    def test_profit_floor_is_inclusive_and_roi_stays_ten_percent(self):
        base=dict(roi=.10,stress=1,cost=100_000_000,
                  crystal_share=0,category_required=True)
        self.assertFalse(eligible_contract_research(net_profit=49_999_999,**base))
        self.assertTrue(eligible_contract_research(net_profit=50_000_000,**base))
        self.assertFalse(eligible_contract_research(
            net_profit=50_000_000,**{**base,"roi":.0999999}))


class ContractMailIntegrationTests(unittest.TestCase):
    def test_mail_and_total_only_count_qualifying_noncrystal_leads(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            folder=root/"runs"/"20261016T012300Z-abc"
            folder.mkdir(parents=True)
            (folder/"manifest.json").write_text(json.dumps({
                "status":"SHADOW_RECORDED","mail_enabled":False,
                "ready_for_production":False
            }),encoding="utf-8")
            (folder/"deep_shadow.json").write_text(json.dumps({
                "status":"SHADOW_ONLY_NO_LIVE_ALERTS",
                "contract_pricing_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT",
                "contract_crystal_screen_basis":CRYSTAL_SHARE_BASIS,
                "contract_approved_locations_examined":5
            }),encoding="utf-8")
            rows=[]
            for i,(profit,share) in enumerate((
                (49_999_999,0.0), (50_000_000,1.0),
                (75_000_000,.5),(65_000_000,.15),
                (77_000_000,None))):
                rows.append({
                    "kind":"contract","contract_id":239000000+i,
                    "reason":"BELOW_GATE_OR_STRESS","status":"WATCH",
                    "net_profit":profit,"roi":.2,"stress_profit":30_000_000,
                    "cost":200_000_000,
                    "source_location":JITA,"destination_location":JITA,
                    "valuation_location_id":JITA,
                    "valuation_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE",
                    "included_items":{"34":1},"energy_crystal_value_share":share,
                    "energy_crystal_share_verified":share is not None
                })
            (folder/"all_proofs.jsonl").write_text(
                "".join(json.dumps(x)+"\n" for x in rows),encoding="utf-8")
            report=make_review(root,limit=None)
            self.assertEqual(report["contract_proofs_audited"],5)
            self.assertEqual(report["research_leads_total"],1)
            self.assertEqual(report["research_leads"][0]["contract_id"],239000003)
            self.assertEqual(report["contract_min_net_profit_isk"],CONTRACT_MIN_NET_ISK)


if __name__=="__main__":
    unittest.main()
