"""Offline ESI archive audit contract; no ESI call and no core V4 mutation."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from v4.esi_market_depth_audit import (
    OfflineAuditError, _top_five, _depth_audit, audit
)

RUN="20261017T220739Z-69e03d4c"
JITA=60003760


class OfflineESIDepthAuditTests(unittest.TestCase):
    def fixture(self, root, *,status="PUBLIC_ESI_REGIONS_COMPLETE"):
        folder=Path(root)/"esi-parallel-validation"/RUN
        folder.mkdir(parents=True)
        report={
            "run":RUN,"status":status,"full_universe_requested":True,
            "failed_regions":[],"unverified_404_regions":[],
            "esi_unique_orders":4,
            "comparison":{"everef_orders":4},
            "reference":{"last_modified":"2026-10-17T14:21:20Z"},
            "esi_cache_freshness":{"oldest_age_minutes":12},
        }
        (folder/"report.json").write_text(json.dumps(report),encoding="utf-8")
        con=sqlite3.connect(folder/"comparison.sqlite3")
        schema="""CREATE TABLE esi (order_id INTEGER PRIMARY KEY,
                region_id INTEGER, location_id INTEGER, type_id INTEGER,
                is_buy_order INTEGER, price REAL, volume_remain INTEGER);
                CREATE TABLE everef (order_id INTEGER PRIMARY KEY,
                region_id INTEGER, location_id INTEGER, type_id INTEGER,
                is_buy_order INTEGER, price REAL, volume_remain INTEGER);"""
        con.executescript(schema)
        con.executemany("INSERT INTO esi VALUES(?,?,?,?,?,?,?)",[
            (1,10000002,JITA,34,1,100,5),
            (2,10000002,JITA,34,1,95,10),
            (3,10000027,60000001,300,0,25,2),
            (5,10000002,JITA,36,1,12,3),
        ])
        con.executemany("INSERT INTO everef VALUES(?,?,?,?,?,?,?)",[
            (1,10000002,JITA,34,1,90,7),
            (2,10000002,JITA,34,1,95,10),
            (4,10000027,60000002,300,0,24,6),
            (6,10000002,JITA,35,1,17,9),
        ])
        con.commit()
        con.close()
        return folder

    def test_all_comparisons_are_from_saved_database_not_network(self):
        with tempfile.TemporaryDirectory() as td:
            folder=self.fixture(td)
            db=folder/"comparison.sqlite3"
            original=db.read_bytes()
            info,out=audit(Path(td),RUN)
            self.assertTrue(out.is_file())
            self.assertEqual(info["status"],"READ_ONLY_OFFLINE_DEPTH_AUDIT")
            self.assertEqual(info["input_esi"],4)
            self.assertEqual(info["input_everef"],4)
            self.assertEqual(info["matched_order_ids"],2)
            self.assertEqual(info["matched_share_of_esi_pct"],50.0)
            self.assertEqual(info["network_calls"],0)
            self.assertFalse(info["same_v4_profit_algorithm_executed"])
            self.assertFalse(info["mail_sent"])
            self.assertFalse(info["market_source_switched"])
            self.assertEqual(db.read_bytes(),original)
            byregion={r["region_id"]:r for r in
                      info["selected_region_unmatched_location_breakdown"]}
            self.assertEqual(byregion[10000027]["everef_only_total"],1)
            self.assertEqual(byregion[10000027]["esi_only_total"],1)
            self.assertEqual(byregion[10000027]["everef_only_locations"][0]
                             ["location_id"],60000002)
            book=info["jita_buy_depth"]
            self.assertEqual(book["both_sources_with_buy_orders"],1)
            self.assertEqual(book["only_esi_type_count"],1)
            self.assertEqual(book["only_everef_type_count"],1)
            self.assertEqual(book["best_bid_changed_type_count"],1)
            self.assertEqual(book["top_best_bid_change_types"][0]
                             ["type_id"],34)
            self.assertEqual(book["top_best_bid_change_types"][0]
                             ["esi_best_bid"],100)
            self.assertEqual(book["top_best_bid_change_types"][0]
                             ["everef_best_bid"],95)
            with self.assertRaisesRegex(OfflineAuditError,"ALREADY_EXISTS"):
                audit(Path(td),RUN)

    def test_incomplete_source_or_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            self.fixture(td,status="INCOMPLETE_ESI_REGIONS")
            with self.assertRaisesRegex(OfflineAuditError,"NOT_PROVEN"):
                audit(Path(td),RUN)
            with self.assertRaisesRegex(OfflineAuditError,"INVALID_ESI_RUN_NAME"):
                audit(Path(td),"../../runs/other")

    def test_top_five_distinct_price_levels_not_five_orders(self):
        six=[(100-i,100+i,2) for i in range(6)]
        result=_top_five(six)
        self.assertEqual(result["five_distinct_price_levels"],5)
        self.assertEqual(result["five_level_order_count"],10)
        self.assertEqual(result["five_level_quantity"],510)

    def test_depth_changed_with_same_best_price_detected(self):
        lhs={34:[(100,10,1)],35:[(50,2,1)]}
        rhs={34:[(100,9,2)],36:[(40,8,1)]}
        out=_depth_audit(lhs,rhs)
        self.assertEqual(out["both_sources_with_buy_orders"],1)
        self.assertEqual(out["best_bid_changed_type_count"],0)
        self.assertEqual(out["five_price_level_quantity_changed_type_count"],1)
        self.assertEqual(out["only_esi_type_samples"],[35])
        self.assertEqual(out["only_everef_type_samples"],[36])


if __name__=="__main__":
    unittest.main()
