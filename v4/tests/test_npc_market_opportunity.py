"""No-network regressions: NPC source completeness and formal-lane integration."""
import gzip
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import patch

from v4.engine import Order
from v4.esi_private_source_jita_ab import JITA, ParityError, STRUCTURES
from v4.npc_market_opportunity import (
    REGIONS, NPC_REGIONS, fresh_public_books, evaluate_npc,
)
from v4.opportunity_push import _current_opportunities

CLOCK = datetime(2026, 10, 23, 2, 0, tzinfo=timezone.utc)
RUN = "20261023T015500Z-cafe1234"
FIELDS = ["order_id", "region_id", "location_id", "type_id", "is_buy_order",
          "price", "volume_remain", "min_volume", "range", "volume_total"]


def order(oid, lid, typ, buy, price, *, region=None):
    return dict(order_id=oid, region_id=region, location_id=lid, type_id=typ,
                is_buy_order=buy, price=price, volume_remain=5,
                min_volume=1, range="station", volume_total=5)


def fixture(root, *, corrupt=None, age_minutes=5):
    stamp = format_datetime(CLOCK - timedelta(minutes=age_minutes), usegmt=True)
    rows = {
        10000002: [order(1, JITA, 1111, 1, 150_000_000, region=10000002)],
        10000032: [order(2, 60011866, 1111, 0, 60_000_000, region=10000032)],
        10000043: [order(3, 60008494, 1111, 0, 65_000_000, region=10000043)],
    }
    if corrupt == "duplicate":
        rows[10000043][0]["order_id"] = 2
    if corrupt == "wrong_region":
        rows[10000043][0]["region_id"] = 10000032
    directory = Path(root) / "esi-parallel-validation" / RUN
    (directory / "regions").mkdir(parents=True)
    regional = []
    for region, data in sorted(rows.items()):
        regional.append({"region_id": region, "status": "COMPLETE",
                         "pages": 1, "orders": len(data), "last_modified": stamp})
        with gzip.open(directory / "regions" / f"{region}.jsonl.gz", "wt") as out:
            for item in data:
                out.write(json.dumps(item) + "\n")
    report = {"run": RUN, "status": "PARTIAL_REGION_TEST_ONLY",
              "requested_region_ids": list(REGIONS),
              "attempted_regions": len(REGIONS),
              "full_universe_requested": False,
              "failed_regions": [], "unverified_404_regions": [],
              "regions": regional, "archive_execution_fields": FIELDS,
              "esi_unique_orders": sum(len(x) for x in rows.values())}
    (directory / "report.json").write_text(json.dumps(report))
    return report


class Catalog:
    def volume(self, item):
        return 1.0


class NpcSourceTests(unittest.TestCase):
    def test_verified_three_regions_and_correct_station_sides(self):
        with tempfile.TemporaryDirectory() as td:
            report = fixture(td)
            jita, npc, jita_evidence, npc_health = fresh_public_books(
                td, report, now=CLOCK)
            self.assertEqual(sum(map(len, jita.values())), 1)
            self.assertEqual(sum(map(len, npc.values())), 2)
            self.assertEqual(set(npc_health), {"Amarr", "Dodixie"})
            self.assertEqual(npc_health["Amarr"]["status"], "COMPLETE")
            self.assertEqual(jita_evidence["jita_buy_orders"], 1)
            self.assertNotIn((JITA, 1111, False), npc)

    def test_reject_partial_region_and_stale_and_malformed_archive(self):
        for fault in ("missing", "stale", "duplicate", "wrong_region"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as td:
                report=fixture(td, corrupt=fault if fault in
                               ("duplicate", "wrong_region") else None,
                               age_minutes=30 if fault=="stale" else 5)
                if fault=="missing":
                    path=(Path(td) / "esi-parallel-validation" / RUN /
                          "regions" / "10000043.jsonl.gz")
                    path.unlink()
                with self.assertRaises(ParityError):
                    fresh_public_books(td,report,now=CLOCK)

    def test_npc_evaluator_reuses_market_proof_and_dedicated_station_labels(self):
        a=Order.parse(order(4, 60008494, 1111, 0, 60_000_000))
        b=Order.parse(order(5, 60011866, 1111, 0, 65_000_000))
        j=Order.parse(order(6, JITA, 1111, 1, 150_000_000))
        books={(60008494,1111,False):[a],(60011866,1111,False):[b]}
        bids={(JITA,1111,True):[j]}
        fake={"status":"MAIL", "reason":"FORMAL_GATE_PASSED", "quantity":1,
              "profit":65_000_000, "roi":.2, "stress_profit":60_000_000,
              "haul":10_000_000,
              "source_vwap_isk_per_unit":60_000_000,
              "jita_vwap_isk_per_unit":150_000_000}
        with patch("v4.npc_market_opportunity.market_proof",return_value=fake) as proof:
            items, counts, by = evaluate_npc(
                books,bids,Catalog(),lambda src,dst,vol:10_000_000)
        self.assertEqual(proof.call_count,2)
        self.assertEqual(counts["MODEL_PASS_RESEARCH_ONLY"],2)
        self.assertIn("Amarr:1111",items)
        self.assertIn("Dodixie:1111",items)
        self.assertEqual(by["Amarr"]["sell_types"],1)
        self.assertEqual(by["Dodixie"]["sell_types"],1)
        for call in proof.call_args_list:
            self.assertEqual(call.kwargs["destination_location"],JITA)

    def test_formal_lanes_merge_npc_without_changing_private_lane(self):
        with tempfile.TemporaryDirectory() as td:
            report=fixture(td)
            jita,npc,_,_=fresh_public_books(td,report,now=CLOCK)
            private_station=next(iter(STRUCTURES.values()))
            private={(private_station,1111,False):[
                Order.parse(order(7,private_station,1111,0,70_000_000))]}
            health={lane:{"status":"COMPLETE","orders":1,
                          "pages":1,"location":station}
                    for lane,station in STRUCTURES.items()}
            # Private mock returns a single source while health is only
            # transport metadata; no live worker credentials are touched.
            with (patch("v4.opportunity_push._private_asks",
                        return_value=(private,{"active_sell_orders":1},{})),
                  patch("v4.opportunity_push._evaluate",
                        return_value=({},{"evaluated_private_sell_type_pairs":1},{}))):
                data=_current_opportunities(
                    Path(td),run_esi=lambda:(report,Path(td)),
                    fetch_private=lambda:([],health),
                    catalog=Catalog(),haul_fn=lambda *_:10_000_000,now=CLOCK)
            self.assertEqual(data["npc_source_health"]["Amarr"]["status"],"COMPLETE")
            self.assertEqual(data["npc_source_health"]["Dodixie"]["status"],"COMPLETE")
            self.assertEqual(set(data["by_station"]),{"Amarr","Dodixie"})
            self.assertEqual(data["esi_jita"]["source_lanes"][-2:],["Amarr","Dodixie"])
            # One unit profit may fail 50M stress when best bid disappears;
            # proving both NPCs entered the existing model is sufficient.
            self.assertEqual(data["npc_model_counts"]["evaluated_npc_sell_type_pairs"],2)


if __name__=="__main__":
    unittest.main()
