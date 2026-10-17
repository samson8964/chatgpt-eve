"""Deterministic offline SAME V4 engine shadow parity; zero market API or mail."""
from __future__ import annotations

import bz2
import csv
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from v4.esi_same_engine_market_shadow import (
    ParityError, audit, JITA, SOURCES
)

RUN="20261017T223910Z-0854a10e"
REF="20261017T210000Z-abcd1234"
FIELDS=("order_id","region_id","location_id","type_id","is_buy_order",
        "price","volume_remain","min_volume","range","volume_total")


def row(id,region,location,buy,price,n,type_id=34,min_vol=1):
    return {"order_id":id,"region_id":region,"location_id":location,
            "type_id":type_id,"is_buy_order":buy,
            "price":price,"volume_remain":n,"min_volume":min_vol,
            "range":"station","volume_total":n}


class Catalog:
    def volume(self,typ):
        return 1.0


def create_fixtures(root, *,omit_execution_fields=False):
    folder=Path(root)/"esi-parallel-validation"/RUN
    (folder/"regions").mkdir(parents=True)
    r_jita=10000002
    r_source=10000043
    amarr=SOURCES[0]
    orders_jita=[
        row(1,r_jita,JITA,True,10_000_000,25),
        row(2,r_jita,JITA,True,9_000_000,25),
    ]
    orders_amarr=[row(3,r_source,amarr,False,1_000_000,20)]
    for reg,records in [(r_jita,orders_jita),(r_source,orders_amarr)]:
        with gzip.open(folder/"regions"/f"{reg}.jsonl.gz","wt",
                       encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record)+"\n")
    report={
        "run":RUN,"status":"PUBLIC_ESI_REGIONS_COMPLETE",
        "full_universe_requested":True,"universe_regions":2,
        "esi_unique_orders":3,"failed_regions":[],
        "unverified_404_regions":[],
        "archive_execution_fields":(
            [] if omit_execution_fields else list(FIELDS)),
        "regions":[
            {"region_id":r_jita,"orders":2,"status":"COMPLETE"},
            {"region_id":r_source,"orders":1,"status":"COMPLETE"}],
        "reference":{"run":REF,"last_modified":"2026-10-17T14:21:20Z"},
        "esi_cache_freshness":{"oldest_age_minutes":10}
    }
    (folder/"report.json").write_text(json.dumps(report),encoding="utf-8")
    ref_folder=Path(root)/"runs"/REF
    (ref_folder/"source").mkdir(parents=True)
    (ref_folder/"manifest.json").write_text(
        '{"status":"SHADOW_RECORDED"}',encoding="utf-8")
    historical=[
        row(1,r_jita,JITA,True,5_000_000,25),
        row(2,r_jita,JITA,True,4_900_000,25),
        row(3,r_source,amarr,False,1_000_000,20),
    ]
    with bz2.open(ref_folder/"source"/"market_orders.csv.bz2","wt",
                  newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(FIELDS))
        w.writeheader()
        w.writerows(historical)
    return folder,ref_folder


class EsiSameV4MarketShadowTests(unittest.TestCase):
    def test_two_snapshots_use_same_engine_and_never_mail(self):
        with tempfile.TemporaryDirectory() as td:
            folder,ref=create_fixtures(td)
            original_report=(folder/"report.json").read_bytes()
            original_archive=(folder/"regions"/"10000002.jsonl.gz").read_bytes()
            haul_fn=Mock(side_effect=lambda src,dst,volume:2_000_000)
            with patch("v4.esi_same_engine_market_shadow._route_evidence"
                       ) as route_calls:
                result,out=audit(Path(td),RUN,catalog=Catalog(),
                    haul_fn=haul_fn,route_evidence={"fixture":True})
            route_calls.assert_not_called()
            self.assertEqual(result["status"],
                             "SHADOW_SAME_V4_ENGINE_PUBLIC_NPC_ONLY")
            self.assertFalse(result["mail_sent"])
            self.assertFalse(result["production_market_source_changed"])
            self.assertEqual(result["economic_logic"],
                "v4.engine.market_proof + v4.market_execution.gross_depth_upper_bound + v4.deep_scan.haul")
            self.assertEqual(result["esi_model_counts"]["PREFILTER_PASSED"],1)
            self.assertEqual(result["everef_model_counts"]["PREFILTER_PASSED"],1)
            self.assertEqual(
                result["comparison"]["classification_counts"]
                ["BOTH_FORMAL_GATE"],1)
            trade=result["comparison"]["all_gate_positive_pairs"][0]
            self.assertTrue(trade["esi"]["policy_passed_shadow_only"])
            self.assertTrue(trade["everef"]["policy_passed_shadow_only"])
            self.assertEqual(trade["esi"]["quantity"],20)
            self.assertEqual(trade["everef"]["quantity"],20)
            self.assertGreater(trade["esi"]["profit"],trade["everef"]["profit"])
            self.assertEqual((folder/"report.json").read_bytes(),original_report)
            self.assertEqual((folder/"regions"/"10000002.jsonl.gz").read_bytes(),
                             original_archive)
            self.assertTrue(out.is_file())
            self.assertTrue(haul_fn.called)
            with self.assertRaisesRegex(ParityError,"ALREADY_EXISTS"):
                audit(Path(td),RUN,catalog=Catalog(),haul_fn=haul_fn,
                      route_evidence={"fixture":True})

    def test_old_archives_without_execution_fields_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            create_fixtures(td,omit_execution_fields=True)
            with self.assertRaisesRegex(ParityError,"RESCAN_REQUIRED"):
                audit(Path(td),RUN,catalog=Catalog(),haul_fn=Mock(),
                      route_evidence={"fixture":True})

    def test_incomplete_regions_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            folder,_=create_fixtures(td)
            doc=json.loads((folder/"report.json").read_text("utf-8"))
            doc["regions"][1]["status"]="FAILED"
            (folder/"report.json").write_text(json.dumps(doc),encoding="utf-8")
            with self.assertRaisesRegex(ParityError,"COVERAGE_INCOMPLETE"):
                audit(Path(td),RUN,catalog=Catalog(),haul_fn=Mock(),
                      route_evidence={"fixture":True})

    def test_missing_reference_or_noncanonical_run_cannot_proceed(self):
        with tempfile.TemporaryDirectory() as td:
            folder,ref=create_fixtures(td)
            (ref/"source"/"market_orders.csv.bz2").unlink()
            with self.assertRaisesRegex(ParityError,"PINNED_EVEREF_SNAPSHOT_MISSING"):
                audit(Path(td),RUN,catalog=Catalog(),haul_fn=Mock(),
                      route_evidence={"fixture":True})
            with self.assertRaisesRegex(ParityError,"INVALID_ESI_RUN_ID"):
                audit(Path(td),"../../main",catalog=Catalog(),haul_fn=Mock(),
                      route_evidence={"fixture":True})


if __name__=="__main__":
    unittest.main()
