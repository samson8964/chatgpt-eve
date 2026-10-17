"""No-secret, no-mail, one authenticated PRIVATE ASK snapshot vs Jita A/B."""
from __future__ import annotations

import json
import gzip
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from unittest.mock import Mock, patch

from v4.engine import Order
from v4.esi_private_source_jita_ab import (
    STRUCTURES, JITA, ParityError, _private_asks, _evaluate, audit,
    _fresh_jita_books
)

RUN="20261017T231839Z-9c24d05b"
REF="20261017T152301Z-acd96c27"


def record(i,loc,buy,price,remaining=20,typ=34):
    return dict(order_id=i,location_id=loc,is_buy_order=buy,
                type_id=typ,price=price,volume_remain=remaining,
                min_volume=1,range="station")


def books(price_a,price_b):
    from collections import defaultdict
    out=defaultdict(list)
    out[(JITA,34,True)]=[
        Order.parse(record(20,JITA,True,price_a)),
        Order.parse(record(21,JITA,True,price_b))]
    return out


def input_private():
    rows=[record(11,STRUCTURES["4-H"],False,1_000_000),
          record(12,STRUCTURES["4-H"],True,900_000)]
    health={
        "four_h":{"status":"COMPLETE","orders":2,"pages":1,
                  "location":STRUCTURES["4-H"]},
        "cj":{"status":"COMPLETE","orders":0,"pages":1,
              "location":STRUCTURES["C-J"]},
        "o4t":{"status":"COMPLETE","orders":0,"pages":1,
               "location":STRUCTURES["O4T"]},
    }
    rows[0]["mock_secret_do_not_log"]="SENSITIVE_BRIDGE_RESPONSE"
    return rows,health


class Catalog:
    def volume(self,typ):
        return 1


class PrivateSourceABTests(unittest.TestCase):
    def test_private_book_accounting_and_privacy(self):
        raw,health=input_private()
        book,counts,hashes=_private_asks(raw,health)
        self.assertEqual(counts["all_active_orders"],2)
        self.assertEqual(counts["active_sell_orders"],1)
        self.assertEqual(counts["active_buy_orders_excluded"],1)
        self.assertEqual(len(hashes),3)
        self.assertEqual(len(book),1)
        self.assertEqual(len(hashes[str(STRUCTURES["C-J"])]),64)
        # Failed structure is not silently dropped from candidate scope.
        health["cj"]["status"]="FAILED"
        with self.assertRaisesRegex(ParityError,"PRIVATE_STRUCTURE_LANE_FAILED"):
            _private_asks(raw,health)

    def test_same_source_asks_produce_different_bids_only(self):
        raw,health=input_private()
        asks,_,_=_private_asks(raw,health)
        esi,counts,_=_evaluate(asks,books(10_000_000,8_000_000),
                             Catalog(),lambda s,d,v:10_000_000)
        ref,counts_old,_=_evaluate(asks,books(4_200_000,4_000_000),
                                 Catalog(),lambda s,d,v:10_000_000)
        self.assertEqual(counts["PREFILTER_PASSED"],1)
        self.assertEqual(counts_old["PREFILTER_PASSED"],1)
        p=esi["4-H:34"]
        q=ref["4-H:34"]
        self.assertTrue(p["hypothetical_model_pass"])
        self.assertFalse(q["hypothetical_model_pass"])
        self.assertGreater(p["net_profit_isk"],q["net_profit_isk"])
        self.assertEqual(p["quantity"],q["quantity"])
        self.assertFalse("ask_order_ids" in p)

    def test_archive_outputs_no_private_raw_and_no_mail(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)/"esi-parallel-validation"/RUN
            folder.mkdir(parents=True)
            report={
                "run":RUN,"status":"SHADOW_MULTI_EPOCH_REPAIRED_COVERAGE",
                "failed_regions":[],"unverified_404_regions":[],
                "reference":{"run":REF,"last_modified":"2026-10-17T14:21:20Z"},
                "esi_cache_freshness":{"span_minutes":25.62},
            }
            (folder/"report.json").write_text(json.dumps(report),encoding="utf-8")
            ref_folder=Path(td)/"runs"/REF
            (ref_folder/"source").mkdir(parents=True)
            (ref_folder/"source"/"market_orders.csv.bz2").write_bytes(b"immutable")
            (ref_folder/"manifest.json").write_text(
                '{"status":"SHADOW_RECORDED"}',encoding="utf-8")
            raw,health=input_private()
            auth=Mock(return_value=(raw,health))
            original_report=(folder/"report.json").read_bytes()
            with patch("v4.esi_private_source_jita_ab._load_esi",
                       return_value=(books(10_000_000,8_000_000),{
                           "all_archived":1558903})) as load_esi,\
                 patch("v4.esi_private_source_jita_ab._load_ref",
                       return_value=(books(4_200_000,4_000_000),{
                           "all_archived":1590547})) as load_ref:
                result,output=audit(Path(td),RUN,fetch_structures=auth,
                    catalog=Catalog(),haul_fn=lambda s,d,v:10_000_000)
            self.assertEqual(auth.call_count,1)
            self.assertEqual(load_esi.call_count,1)
            self.assertEqual(load_ref.call_count,1)
            self.assertEqual(result["esi_model_counts"]["MODEL_PASS_RESEARCH_ONLY"],1)
            self.assertEqual(result["everef_model_counts"]["REJECT_BELOW_GATE_OR_STRESS"],1)
            self.assertEqual(result["comparison"]["classification_counts"]
                             ["ESI_ONLY_PASS"],1)
            self.assertFalse(result["mail_sent"])
            self.assertFalse(result["production_source_changed"])
            self.assertFalse(result["private_raw_rows_persisted"])
            self.assertEqual((folder/"report.json").read_bytes(),original_report)
            doc=output.read_text("utf-8")
            self.assertNotIn("SENSITIVE_BRIDGE_RESPONSE",doc)
            self.assertNotIn('"order_id": 11',doc)
            self.assertNotIn('"order_id": 12',doc)
            self.assertIn("4-H:34",doc)

    def test_fresh_verified_jita_archive_enforces_age_and_full_region(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/"esi-parallel-validation"/"20261017T230000Z-1234abcd"
            (target/"regions").mkdir(parents=True)
            clock=datetime(2026,10,17,23,10,tzinfo=timezone.utc)
            report={
                "run":target.name,"status":"PARTIAL_REGION_TEST_ONLY",
                "requested_region_ids":[10000002],
                "attempted_regions":1,"full_universe_requested":False,
                "failed_regions":[],"unverified_404_regions":[],
                "archive_execution_fields":[
                    "order_id","region_id","location_id","type_id",
                    "is_buy_order","price","volume_remain","min_volume",
                    "range","volume_total"],
                "regions":[{
                    "region_id":10000002,"status":"COMPLETE",
                    "orders":2,"pages":1,
                    "last_modified":format_datetime(clock-timedelta(minutes=5),
                                                   usegmt=True)}],
                "esi_unique_orders":2,
            }
            (target/"report.json").write_text(json.dumps(report),encoding="utf-8")
            with gzip.open(target/"regions"/"10000002.jsonl.gz",
                           "wt",encoding="utf-8") as fh:
                for order in (record(81,JITA,True,12e6),
                              record(82,STRUCTURES["4-H"],False,1e6)):
                    order["region_id"]=10000002
                    order["volume_total"]=order["volume_remain"]
                    fh.write(json.dumps(order)+"\n")
            books,counts,meta=_fresh_jita_books(
                Path(td),target.name,now=clock)
            self.assertEqual(meta["age_at_private_comparison_minutes"],5)
            self.assertEqual(meta["jita_buy_orders"],1)
            self.assertEqual(counts["forge_active_orders"],2)
            self.assertEqual(len(books[(JITA,34,True)]),1)
            with self.assertRaisesRegex(ParityError,"TOO_OLD"):
                _fresh_jita_books(Path(td),target.name,
                                  now=clock+timedelta(minutes=12))
            report["regions"][0]["status"]="FAILED"
            (target/"report.json").write_text(json.dumps(report),encoding="utf-8")
            with self.assertRaisesRegex(ParityError,"INCOMPLETE"):
                _fresh_jita_books(Path(td),target.name,now=clock)

    def test_fresh_jita_ab_uses_only_region_book_not_old_combined_book(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)/"esi-parallel-validation"/RUN
            folder.mkdir(parents=True)
            report={
                "run":RUN,"status":"SHADOW_MULTI_EPOCH_REPAIRED_COVERAGE",
                "failed_regions":[],"unverified_404_regions":[],
                "reference":{"run":REF,"last_modified":"2026-10-17T14:21:20Z"},
                "esi_cache_freshness":{"span_minutes":25.62},
            }
            (folder/"report.json").write_text(json.dumps(report),encoding="utf-8")
            ref_folder=Path(td)/"runs"/REF
            (ref_folder/"source").mkdir(parents=True)
            (ref_folder/"source"/"market_orders.csv.bz2").write_bytes(b"immutable")
            (ref_folder/"manifest.json").write_text(
                '{"status":"SHADOW_RECORDED"}',encoding="utf-8")
            raw,health=input_private()
            with patch("v4.esi_private_source_jita_ab._load_esi") as old_esi, \
                 patch("v4.esi_private_source_jita_ab._load_ref",
                       return_value=(books(4_200_000,4_000_000),{
                           "all_archived":1590547})), \
                 patch("v4.esi_private_source_jita_ab._fresh_jita_books",
                       return_value=(books(10_000_000,8_000_000),
                           {"forge_active_orders":403199},
                           {"archive_run":"20261017T233000Z-abcd1234",
                            "last_modified":"2026-10-17T23:28:00Z",
                            "age_at_private_comparison_minutes":5})):
                result,out=audit(Path(td),RUN,fetch_structures=lambda:(raw,health),
                    catalog=Catalog(),haul_fn=lambda s,d,v:10_000_000,
                    fresh_jita_run="20261017T233000Z-abcd1234")
            old_esi.assert_not_called()
            self.assertEqual(result["status"],
                             "READ_ONLY_PRIVATE_SOURCE_FRESH_JITA_BUY_AB")
            self.assertEqual(result["esi_price_feed_kind"],
                             "FRESH_VERIFIED_THE_FORGE_REGION_JITA_BUYS")
            self.assertEqual(result["comparison"]["classification_counts"]
                             ["ESI_ONLY_PASS"],1)
            self.assertFalse(result["mail_sent"])
            self.assertFalse(result["production_source_changed"])
            self.assertIn("private_source_jita_fresh_ab_",out.name)
            self.assertNotIn("SENSITIVE_BRIDGE_RESPONSE",out.read_text("utf-8"))

    def test_unverified_private_lane_blocks_all_comparisons(self):
        raw,health=input_private()
        health["o4t"]["status"]="FAILED"
        with self.assertRaisesRegex(ParityError,"PRIVATE_STRUCTURE_LANE_FAILED"):
            _private_asks(raw,health)
        bad=raw+[raw[0]]
        with self.assertRaisesRegex(ParityError,"PRIVATE_STRUCTURE_ORDER_COUNT_MISMATCH"):
            _private_asks(bad,input_private()[1])


if __name__=="__main__":
    unittest.main()
