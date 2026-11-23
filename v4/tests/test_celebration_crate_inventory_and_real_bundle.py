"""No-network checks for historical PLEX candidate review and actual-data math."""
import json
import tarfile
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from v4.celebration_crate_inventory import (
    analyze_type_rows, from_archive, known_registry,
)
from v4.celebration_crate_real_bundle_audit import audit_rows
from v4.celebration_crate_radar import BOXES, JITA


class FakeCatalog:
    def volume(self, tid):
        return 3.0
    def classification(self, tid):
        return "blueprint_type" if tid == 90001 else "regular"


class HistoricalCrateDiscoveryTests(unittest.TestCase):
    def test_known_nontradable_and_unknown_are_not_auto_approved(self):
        reg=known_registry()
        self.assertEqual(reg[53530]["documented_plex"],100)
        self.assertEqual(reg[53530]["classification"],"NON_TRADEABLE")
        self.assertIsNone(reg[63097]["documented_plex"])
        self.assertEqual(reg[63097]["classification"],"PLEX_QTY_UNKNOWN")
        self.assertFalse(set(BOXES) & set(reg))

    def test_sde_candidates_with_guaranteed_random_and_excluded(self):
        raw={
            "80240":{"name":{"en":"Yoiul Festival Celebration Crate"},
                     "description":{"en":"This crate contains 20 PLEX."}},
            "123321":{"name":{"en":"Historical PLEX Celebration Crate"},
                      "description":{"en":"This crate contains 15 PLEX and fireworks."}},
            "123322":{"name":{"en":"Ancient New Eden Reward Box"},
                      "description":{"en":"One of several items can drop, including PLEX."}},
            "123323":{"name":{"en":"Nontradable Gift Box"},
                      "description":{"en":"Contains 20 PLEX. This item cannot be traded."}},
            "123324":{"name":{"en":"Mystery Gift Box"},
                      "description":{"en":"May contain a random battleship SKIN only."}},
        }
        r=analyze_type_rows(raw,registry={})
        status={x["type_id"]:x["status"] for x in r["entries"]}
        self.assertEqual(status[80240],"ACTIVE_APPROVED")
        self.assertEqual(status[123321],"DISCOVERED_FIXED_PLEX_CANDIDATE_REVIEW")
        self.assertEqual(status[123322],"DISCOVERED_RANDOM_PLEX_CANDIDATE_REVIEW")
        self.assertEqual(status[123323],"DISCOVERED_NON_TRADEABLE")
        self.assertNotIn(123324,status)
        self.assertFalse(next(x for x in r["entries"] if x["type_id"]==123321)["active_scanner"])

    def test_archive_has_types_and_version_hash(self):
        types={"80240":{"name":"Yoiul Festival Celebration Crate",
                        "description":{"en":"This crate contains 20 PLEX."}},
               "50000":{"name":"No PLEX in this Label","description":"a civilian item"}}
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"sde.tar.xz"
            payload=json.dumps(types).encode("utf-8")
            import io
            with tarfile.open(path,"w:xz") as tar:
                meta=tarfile.TarInfo("types.json")
                meta.size=len(payload)
                tar.addfile(meta,io.BytesIO(payload))
            result=from_archive(path,min_types=1)
        self.assertEqual(result["type_count_in_sde"],2)
        self.assertIn("archive_sha256",result)


def order(oid, tid, price, volume, *, min_vol=1):
    return {"order_id":oid,"type_id":tid,"location_id":JITA,
            "price":price,"volume_remain":volume,
            "min_volume":min_vol,"is_buy_order":True}


class RealBundleEstimatorFixtureTests(unittest.TestCase):
    def setUp(self):
        self.catalog=FakeCatalog()
        self.at=datetime(2026,11,23,2,30,tzinfo=timezone.utc)
        self.market=[order(1,34,10_000_000,2),order(2,34,8_000_000,2),
                     order(3,35,5_000_000,1),
                     order(4,44992,4_878_000,100)]
        self.contracts=[
            {"contract_id":777,"start_location_id":JITA,"type":"item_exchange",
             "price":5_000_000,"date_expired":"2026-12-03T00:00:00Z"},
            {"contract_id":778,"start_location_id":JITA,"type":"item_exchange",
             "price":5_000_000},
            {"contract_id":779,"start_location_id":JITA,"type":"item_exchange",
             "price":5_000_000}
        ]
        self.items=[
            {"contract_id":777,"type_id":34,"quantity":5,"is_included":True},
            {"contract_id":777,"type_id":35,"quantity":4,"is_included":True},
            {"contract_id":778,"type_id":34,"quantity":5,"is_included":True},
            {"contract_id":778,"type_id":35,"quantity":4,"is_included":True},
            {"contract_id":778,"type_id":37,"quantity":1,"is_included":False},
            {"contract_id":779,"type_id":34,"quantity":5,"is_included":True},
            {"contract_id":779,"type_id":90001,"quantity":1,"is_included":True}
        ]

    def audit(self):
        return audit_rows(self.contracts,self.items,self.market,catalog=self.catalog,
                          locations={JITA},at=self.at,max_examples=20,
                          haul_fn=lambda _loc,_volume:0)

    def test_independent_real_order_depth_crosscheck(self):
        result=self.audit()
        self.assertTrue(result["all_cross_checks_passed"])
        self.assertEqual(result["selection_counts"]["eligible_nonblueprint_no_requests"],1)
        self.assertEqual(result["selection_counts"]["with_requested_items_excluded"],1)
        self.assertEqual(result["selection_counts"]["contains_blueprint_excluded"],1)
        evidence=result["examples"][0]
        self.assertEqual(evidence["contract_id"],777)
        self.assertEqual(evidence["actual_included_types"],2)
        self.assertAlmostEqual(evidence["gross_jita_buy_depth_isk"],41_000_000)
        self.assertAlmostEqual(evidence["net_before_haul_isk"],
                               41_000_000*(1-.03375)-5_000_000)
        details={row["type_id"]:row for row in evidence["itemized_actual_jita_order_fills"]}
        self.assertEqual(details[34]["matched_units"],4)
        self.assertEqual(details[34]["remaining_units_unpriced"],1)
        self.assertEqual(details[35]["matched_units"],1)
        self.assertEqual(details[35]["remaining_units_unpriced"],3)
        self.assertEqual([x["order_id"] for x in details[34]["fills"]],[1,2])

    def test_real_crate_plus_other_fixture_not_claimed_historical(self):
        self.contracts=[dict(contract_id=123,start_location_id=JITA,
                             type="item_exchange",price=60_000_000)]
        self.items=[
            dict(contract_id=123,type_id=80240,quantity=1,is_included=True),
            dict(contract_id=123,type_id=34,quantity=3,is_included=True)
        ]
        result=self.audit()
        self.assertEqual(result["real_plex_crate_plus_other_contract_candidates"],1)
        row=result["examples"][0]
        self.assertEqual(row["contract_id"],123)
        self.assertAlmostEqual(row["gross_jita_buy_depth_isk"],
                               20*4_878_000 + 2*10_000_000 + 8_000_000)
        self.assertTrue(row["independent_cross_check_passed"])


if __name__=="__main__":
    unittest.main()
