"""No-network regression checks for V4 archived source freshness audit."""
from __future__ import annotations

import bz2
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from v4.source_freshness_audit import audit, minutes_since, utc


class SourceFreshnessAuditTests(unittest.TestCase):
    def test_timezone_http_timestamp_and_missing_timestamp(self):
        self.assertEqual(
            minutes_since("2026-10-15T16:23:00Z","2026-10-15T15:53:00Z"),30)
        self.assertEqual(
            minutes_since("2026-10-15T16:23:00Z",
                          "Thu, 15 Oct 2026 16:03:00 GMT"),20)
        self.assertIsNone(utc("not-a-timestamp"))
        self.assertIsNone(minutes_since("2026-10-15T16:23:00Z",None))

    def test_completed_local_source_meta_and_all_rows(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            previous=root/"runs"/"20261015T152300Z-aaaa"
            previous.mkdir(parents=True)
            (previous/"manifest.json").write_text('{"status":"SHADOW_RECORDED"}')
            (previous/"full_market_report.json").write_text(
                json.dumps({"sources":{"market_orders":{"sha256":"same"},
                                       "public_contracts":{"sha256":"old"}}}))
            folder=root/"runs"/"20261015T162300Z-bbbb"
            raw=folder/"source"
            raw.mkdir(parents=True)
            (folder/"manifest.json").write_text(
                json.dumps({"status":"SHADOW_RECORDED",
                            "started_at":"2026-10-15T16:23:00Z"}))
            (folder/"full_market_report.json").write_text(
                json.dumps({"overall":"CENSUS_COMPLETE_PROOFS_NOT_READY",
                    "sources":{
                        "market_orders":{
                            "status":"COMPLETE","last_modified":"2026-10-15T16:10:00Z",
                            "age_hours":.2,"sha256":"same","compressed_bytes":42},
                        "public_contracts":{
                            "status":"COMPLETE","last_modified":"2026-10-15T16:00:00Z",
                            "age_hours":.4,"sha256":"new","compressed_bytes":43}},
                    "market":{"market_raw_rows":3},"contracts":{"contract_rows_total":2}}))
            data=("\n".join([
                "location_id,region_id,http_last_modified",
                "60003760,10000002,2026-10-15T16:13:00Z",
                "60003760,10000002,2026-10-15T14:03:00Z",
                "60008494,10000043,2026-10-15T15:53:00Z"
            ])+"\n").encode()
            (raw/"market_orders.csv.bz2").write_bytes(bz2.compress(data))
            with tarfile.open(raw/"public_contracts.tar.bz2","w:bz2") as z:
                obj=json.dumps({"datasource":"tranquility",
                    "scrape_start":"2026-10-15T15:40:00Z",
                    "scrape_end":"2026-10-15T15:55:00Z"}).encode()
                tarinfo=tarfile.TarInfo("sde/meta.json")
                tarinfo.size=len(obj)
                z.addfile(tarinfo,io.BytesIO(obj))
            result=audit(root,deep=True)
            self.assertEqual(result["run"],folder.name)
            self.assertEqual(result["sources"]["market_orders"]
                             ["upload_age_minutes_at_scan"],13)
            self.assertTrue(result["sources"]["market_orders"]
                            ["same_sha256_as_previous_run"])
            self.assertFalse(result["sources"]["public_contracts"]
                             ["same_sha256_as_previous_run"])
            self.assertEqual(result["contract_archive_scrape"]
                             ["scrape_end_age_minutes_at_scan"],28)
            self.assertEqual(result["contract_archive_scrape"]
                             ["scrape_duration_minutes"],15)
            rows=result["market_esi_cache_timestamp_distribution"]
            self.assertEqual(rows["rows"],3)
            self.assertEqual(rows["regions_represented"],2)
            self.assertEqual(rows["esi_http_last_modified_age_minutes"]["oldest"],140)
            self.assertEqual(rows["esi_http_last_modified_age_minutes"]
                             ["rows_older_than_120m"],1)
            self.assertEqual(rows["jita_and_other_npc_station_order_rows"]
                             ["Jita 4-4"],2)

if __name__=="__main__":
    unittest.main()
