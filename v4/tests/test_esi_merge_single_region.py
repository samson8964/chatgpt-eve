"""One failed region may be recovered OFFLINE only, without claiming atomic full snapshot."""
from __future__ import annotations

import gzip
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing

from v4.esi_merge_single_region import MergeError, combine

BASE="20261017T225007Z-79cc75a2"
PATCH="20261017T230000Z-abcd1234"
LOST_REGION=10000028
LIVE_REGION=10000002
EMPTY_REGION=10000004
FIELDS=["order_id","region_id","location_id","type_id","is_buy_order",
        "price","volume_remain","min_volume","range","volume_total"]


def row(oid,region):
    return {"order_id":oid,"region_id":region,"location_id":60003760,
            "type_id":34,"is_buy_order":True,"price":1000,
            "volume_remain":2,"min_volume":1,"range":"station","volume_total":2}


def fixture(root):
    parent=Path(root)/"esi-parallel-validation"
    base=parent/BASE
    patch=parent/PATCH
    for p in [base,patch]:
        (p/"regions").mkdir(parents=True)
    with gzip.open(base/"regions"/f"{LIVE_REGION}.jsonl.gz","wt",
                   encoding="utf-8") as f:
        f.write(json.dumps(row(11,LIVE_REGION))+"\n")
    with gzip.open(base/"regions"/f"{EMPTY_REGION}.jsonl.gz","wt",
                   encoding="utf-8") as f:
        pass
    with gzip.open(patch/"regions"/f"{LOST_REGION}.jsonl.gz","wt",
                   encoding="utf-8") as f:
        f.write(json.dumps(row(22,LOST_REGION))+"\n")
    def reg(rid,status,n,stamp):
        return {
            "region_id":rid,"status":status,"orders":n,
            "pages":1,"last_modified":stamp,
            "exhausted_orders_excluded":0}
    base_reg=[
        reg(LIVE_REGION,"COMPLETE",1,"Sat, 17 Oct 2026 22:45:39 GMT"),
        reg(EMPTY_REGION,"EMPTY_MARKET_CONFIRMED",0,
            "Sat, 17 Oct 2026 22:47:12 GMT"),
        {"region_id":LOST_REGION,"status":"FAILED","orders":0,"pages":0,
         "last_modified":None,"error":"ESI_PAGINATION_VERSION_MISMATCH"}]
    patched_reg=[
        reg(LOST_REGION,"COMPLETE",1,"Sat, 17 Oct 2026 23:01:15 GMT")]
    original={
        "run":BASE,"status":"INCOMPLETE_ESI_REGIONS",
        "full_universe_requested":True,
        "universe_regions":3,"attempted_regions":3,"esi_unique_orders":1,
        "esi_pages":2,"esi_exhausted_orders_excluded":0,
        "failed_regions":[LOST_REGION],"unverified_404_regions":[],
        "archive_execution_fields":FIELDS,
        "regions":base_reg,"reference":{"run":"20261017T210000Z-abcd1234",
                                          "last_modified":"2026-10-17T14:21:20Z"}}
    targeted={
        "run":PATCH,"status":"PARTIAL_REGION_TEST_ONLY",
        "requested_region_ids":[LOST_REGION],"full_universe_requested":False,
        "universe_regions":3,"attempted_regions":1,"esi_unique_orders":1,
        "esi_exhausted_orders_excluded":0,"failed_regions":[],
        "archive_execution_fields":FIELDS,
        "regions":patched_reg}
    (base/"report.json").write_text(json.dumps(original),encoding="utf-8")
    (patch/"report.json").write_text(json.dumps(targeted),encoding="utf-8")
    with closing(sqlite3.connect(base/"comparison.sqlite3")) as db:
        db.executescript("CREATE TABLE esi(order_id INTEGER PRIMARY KEY);")
        db.execute("INSERT INTO esi VALUES(11)")
        db.commit()
    return base,patch


class EsiMergeSingleRegionTests(unittest.TestCase):
    def test_recover_only_one_region_by_lineage_without_editing_source(self):
        with tempfile.TemporaryDirectory() as td:
            base,patch=fixture(td)
            saved_report=(base/"report.json").read_bytes()
            saved_db=(base/"comparison.sqlite3").read_bytes()
            saved_region=(patch/"regions"/f"{LOST_REGION}.jsonl.gz").read_bytes()
            result,output=combine(Path(td),BASE,PATCH)
            self.assertEqual(result["status"],
                             "SHADOW_MULTI_EPOCH_REPAIRED_COVERAGE")
            self.assertEqual(result["esi_unique_orders"],2)
            self.assertEqual(result["universe_regions"],3)
            self.assertEqual(result["attempted_regions"],3)
            self.assertEqual(result["failed_regions"],[])
            self.assertEqual(result["data_source_decision"],
                             "DO_NOT_SWITCH_PRODUCTION")
            self.assertFalse(result["live_mail_allowed"])
            self.assertIsNone(result["comparison"])
            self.assertGreater(result["esi_cache_freshness"]["span_minutes"],5)
            info={r["region_id"]:r for r in result["regions"]}
            self.assertEqual(info[LOST_REGION]["archive_run"],PATCH)
            self.assertEqual(info[LIVE_REGION]["archive_run"],BASE)
            self.assertEqual(info[EMPTY_REGION]["archive_run"],BASE)
            self.assertTrue(output.is_file())
            self.assertEqual((base/"report.json").read_bytes(),saved_report)
            self.assertEqual((base/"comparison.sqlite3").read_bytes(),saved_db)
            self.assertEqual((patch/"regions"/f"{LOST_REGION}.jsonl.gz").read_bytes(),
                             saved_region)

    def test_no_fake_completion_without_verified_patch(self):
        with tempfile.TemporaryDirectory() as td:
            _,patch=fixture(td)
            doc=json.loads((patch/"report.json").read_text("utf-8"))
            doc["regions"][0]["status"]="FAILED"
            (patch/"report.json").write_text(json.dumps(doc),encoding="utf-8")
            with self.assertRaisesRegex(MergeError,"SINGLE_REGION"):
                combine(Path(td),BASE,PATCH)

    def test_duplicate_patch_order_id_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            _,patch=fixture(td)
            with gzip.open(patch/"regions"/f"{LOST_REGION}.jsonl.gz",
                           "wt",encoding="utf-8") as f:
                f.write(json.dumps(row(11,LOST_REGION))+"\n")
            with self.assertRaisesRegex(MergeError,"ALREADY_PRESENT"):
                combine(Path(td),BASE,PATCH)

    def test_path_escape_disallowed(self):
        with tempfile.TemporaryDirectory() as td:
            fixture(td)
            with self.assertRaisesRegex(MergeError,"INVALID_VALIDATION_RUN_ID"):
                combine(Path(td),"../esc",PATCH)

    def test_patch_cannot_hide_base_missing_success_archive(self):
        with tempfile.TemporaryDirectory() as td:
            base,patch=fixture(td)
            (base/"regions"/f"{LIVE_REGION}.jsonl.gz").unlink()
            with self.assertRaisesRegex(MergeError,"BASE_COMPLETE_REGION_ARCHIVE_MISSING"):
                combine(Path(td),BASE,PATCH)


if __name__=="__main__":
    unittest.main()
