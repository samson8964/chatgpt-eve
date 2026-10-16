"""Offline independent ESI cache-version vs EVE Ref market-snapshot comparison."""
from __future__ import annotations

import bz2
import io
import tempfile
import unittest
from pathlib import Path

from v4.upstream_integrity_audit import (
    _sample_status, compare_region, local_market_census, probe_region
)


class IndependentUpstreamAuditTests(unittest.TestCase):
    def test_stream_every_row_and_region_timestamp_distribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/"market_orders.csv.bz2"
            csv=("region_id,order_id,http_last_modified,volume_remain,price,is_buy_order,type_id,location_id\n"
                 "10000060,1,2026-10-16T12:15:00Z,5,100,false,34,60000001\n"
                 "10000060,2,2026-10-16T12:15:00Z,5,110,true,34,60000001\n"
                 "10000043,3,2026-10-16T11:00:00Z,10,50,false,35,60000002\n")
            archive.write_bytes(bz2.compress(csv.encode()))
            data, selected=local_market_census(
                archive,"2026-10-16T12:23:01Z",compare_regions={10000060})
            self.assertEqual(data["rows"],3)
            self.assertEqual(data["region_count_with_orders"],2)
            self.assertEqual(data["duplicate_order_ids_global"],0)
            self.assertEqual(data["regions"]["10000060"]["timestamp_versions"],1)
            self.assertEqual(data["regions"]["10000060"]["cache_age_minutes"]["p90"],8.0)
            self.assertEqual(data["regions"]["10000043"]["rows_older_60m"],1)
            self.assertEqual(len(selected[10000060]),2)

    def test_equal_generation_complete_region_reconciliation(self):
        raw=[
            {"order_id":1,"type_id":34,"location_id":60000001,
             "is_buy_order":False,"volume_remain":5,"price":100},
            {"order_id":2,"type_id":34,"location_id":60000001,
             "is_buy_order":True,"volume_remain":5,"price":110},
        ]
        calls=[]
        def fetch(session,path,params=None):
            page=params["page"]
            calls.append(page)
            value=raw[:1] if page==1 else raw[1:]
            return value, {"Last-Modified":"Fri, 16 Oct 2026 12:15:00 GMT",
                           "X-Pages":"2"},200
        local={"rows":2,"timestamp_versions":1,"missing_timestamp_rows":0,
               "duplicate_order_ids":0,
               "timestamps_newest_first":[{"http_last_modified_utc":"2026-10-16T12:15:00+00:00",
                                           "rows":2}]}
        old={1:("34","60000001",False,"5","100"),
             2:("34","60000001",True,"5","110")}
        result=compare_region(object(),10000060,local,old,fetch=fetch,
                              sleep=lambda _:None)
        self.assertEqual(calls,[1,2])
        self.assertTrue(result["same_esi_cache_generation_as_archive"])
        self.assertEqual(result["verification"],"MATCH_SAME_CACHE_GENERATION")
        self.assertEqual(result["esi_orders_not_in_archive"],0)
        self.assertEqual(result["same_cache_order_details_differ"],0)

    def test_same_generation_missing_one_order_is_definite_discrepancy(self):
        raw=[{"order_id":1,"type_id":34,"location_id":60000001,
              "is_buy_order":False,"volume_remain":5,"price":100}]
        def fetch(session,path,params=None):
            return raw, {"Last-Modified":"Fri, 16 Oct 2026 12:15:00 GMT",
                         "X-Pages":"1"},200
        local={"rows":0,"timestamp_versions":1,"missing_timestamp_rows":0,
               "duplicate_order_ids":0,
               "timestamps_newest_first":[{"http_last_modified_utc":"2026-10-16T12:15:00+00:00",
                                           "rows":1}]}
        result=compare_region(object(),10000060,local,{},fetch=fetch,
                              sleep=lambda _:None)
        self.assertEqual(result["verification"],
                         "DISCREPANCY_SAME_CACHE_GENERATION")
        self.assertEqual(result["esi_orders_not_in_archive"],1)

    def test_different_snapshot_generation_never_claims_missing(self):
        def fetch(session,path,params=None):
            return [{"order_id":50}],{
                "Last-Modified":"Fri, 16 Oct 2026 12:20:00 GMT",
                "X-Pages":"1"},200
        local={"rows":1,"timestamp_versions":1,
               "timestamps_newest_first":[{"http_last_modified_utc":"2026-10-16T12:15:00+00:00",
                                           "rows":1}]}
        result=compare_region(object(),10000060,local,{1:()},fetch=fetch,
                              sleep=lambda _:None)
        self.assertEqual(result["verification"],"INCONCLUSIVE_VERSION_MISMATCH")
        self.assertFalse(result["same_esi_cache_generation_as_archive"])

    def test_cache_change_across_pages_is_inconclusive(self):
        def fetch(session,path,params=None):
            page=params["page"]
            return [{"order_id":page}],{
                "Last-Modified":("Fri, 16 Oct 2026 12:15:00 GMT" if page==1
                                 else "Fri, 16 Oct 2026 12:20:00 GMT"),
                "X-Pages":"2"},200
        local={"rows":2,"timestamp_versions":1,
               "timestamps_newest_first":[{"http_last_modified_utc":"2026-10-16T12:15:00+00:00",
                                           "rows":2}]}
        result=compare_region(object(),10000060,local,{1:(),2:()},
                              fetch=fetch,sleep=lambda _:None)
        self.assertTrue(result["page_version_changed"])
        self.assertEqual(result["verification"],"INCONCLUSIVE_VERSION_MISMATCH")

    def test_oversized_region_not_partial_misrepresented(self):
        def fetch(session,path,params=None):
            return [{"order_id":1}],{
                "Last-Modified":"Fri, 16 Oct 2026 12:15:00 GMT",
                "X-Pages":"501"},200
        result=compare_region(object(),10000060,{}, {},fetch=fetch,
                              sleep=lambda _:None,max_pages=500)
        self.assertEqual(result["verification"],"SKIPPED_PAGE_LIMIT")
        self.assertEqual(result["required_pages"],501)


if __name__=="__main__":
    unittest.main()
