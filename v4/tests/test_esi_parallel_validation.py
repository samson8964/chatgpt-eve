"""Offline mock ESI market census: 404, pagination, freshness, comparisons.

All HTTP is stubbed. No actual ESI, GMail, private market or EVE account is
accessed during CI. Production public requests occur only through explicit
python -m v4.esi_parallel_validation in the user's local shell.
"""
from __future__ import annotations

import bz2
import csv
import json
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

try:
    from v4.esi_parallel_validation import (
        Api, ValidationError, _http_time, _row,
        fetch_region, run, reconcile_saved, STATION_JITA
    )
except ImportError:
    Api=ValidationError=_http_time=_row=fetch_region=run=None
    STATION_JITA=60003760


STAMP="Sat, 17 Oct 2026 20:00:00 GMT"
STAMP_CHANGED="Sat, 17 Oct 2026 20:05:00 GMT"


def item(oid, *,region=10000001, price=1500000,remain=5):
    return {
        "order_id":oid,
        "type_id":34,"location_id":STATION_JITA,
        "is_buy_order":True,"price":price,
        "volume_remain":remain,"volume_total":remain,
        "min_volume":1,"range":"station"
    }


class FakeApi:
    def __init__(self, dirs=None):
        self.calls=[]
        self.counts=Counter()
        self.dirs=dirs or [10000001,10000002,10000003]
        self.version_drift=False
        self.fail_region=False
        self.empty_region=False
        self.exhausted_region=False
        self.invalid_region=False

    def request(self,path,params=None):
        self.calls.append((path,dict(params or {})))
        if path=="/universe/regions/":
            return 200,list(self.dirs),{"last-modified":STAMP}
        region=int(path.split("/")[2])
        if self.fail_region and region==10000002:
            raise ValidationError("ESI_HTTP_503_RETRIES_EXHAUSTED")
        if region==10000002:
            return 404,None,{}
        if region==10000003:
            if self.empty_region:
                rows=[]
            elif self.exhausted_region:
                rows=[item(303,region=region,remain=0)]
            elif self.invalid_region:
                rows=[{**item(303,region=region),"price":0}]
            else:
                rows=[item(303,region=region)]
            n=1
        else:
            n=2
            page=params["page"]
            rows=([item(101)] if page==1 else [item(102)])
        headers={"x-pages":str(n),
                 "last-modified":(
                     STAMP_CHANGED if self.version_drift and
                     region==10000001 and params["page"]==2 else STAMP),
                 "expires":"Thu, 01 Jan 2099 00:00:00 GMT"}
        return 200,rows,headers


def install_ref(root):
    """Store local immutable complete prior run matching V4 source layout."""
    folder=root/"runs"/"20261017T202301Z-abcde123"
    (folder/"source").mkdir(parents=True)
    (folder/"manifest.json").write_text(json.dumps({
        "status":"SHADOW_RECORDED"
    }),encoding="utf-8")
    (folder/"full_market_report.json").write_text(json.dumps({
        "sources":{"market_orders":{"last_modified":"2026-10-17T19:48:00Z"}}
    }))
    source=folder/"source"/"market_orders.csv.bz2"
    with bz2.open(source,"wt",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=["order_id","region_id",
            "location_id","type_id","price","volume_remain","is_buy_order"])
        writer.writeheader()
        writer.writerow(dict(order_id=101,region_id=10000001,
            location_id=STATION_JITA,type_id=34,price=1400000,
            volume_remain=6,is_buy_order="True"))
        writer.writerow(dict(order_id=999,region_id=10000001,
            location_id=STATION_JITA,type_id=34,price=1200000,
            volume_remain=1,is_buy_order="True"))
    return source


@unittest.skipUnless(Api is not None,"requires requests in full V4 Python environment")
class EsiParallelValidationTests(unittest.TestCase):
    def test_esi_row_validation(self):
        self.assertEqual(_row(item(101),10000001)["volume_remain"],5)
        for patch_row in ({"order_id":-1},{"price":0},
                          {"is_buy_order":"true"},{"volume_total":0},
                          {"range":"invalid_range"}):
            with self.subTest(patch_row=patch_row):
                with self.assertRaises(ValidationError):
                    _row({**item(101),**patch_row},10000001)

    def test_exhausted_zero_remaining_is_not_a_tradeable_order(self):
        self.assertIsNone(_row(item(101,remain=0),10000001))
        with self.assertRaisesRegex(ValidationError,"volume_remain"):
            _row(item(101,remain=-1),10000001)
        for patch_row in ({"price":0},{"is_buy_order":"true"},
                          {"volume_total":0}):
            with self.subTest(patch_row=patch_row):
                with self.assertRaises(ValidationError):
                    _row({**item(101),**patch_row},10000001)

    def test_verified_one_page_empty_region_is_not_failed(self):
        with tempfile.TemporaryDirectory() as td:
            fake=FakeApi()
            fake.empty_region=True
            result=fetch_region(fake,10000003,Path(td))
            self.assertEqual(result["status"],"EMPTY_MARKET_CONFIRMED")
            self.assertEqual(result["pages"],1)
            self.assertEqual(result["orders"],0)
            self.assertTrue((Path(td)/"10000003.jsonl.gz").exists())
            report,_=run(Path(td),fetcher=fake,fetch_reference=False)
            self.assertEqual(report["status"],
                             "PUBLIC_ESI_404_COVERAGE_UNVERIFIED")
            self.assertEqual(report["confirmed_empty_regions"],[10000003])
            self.assertEqual(report["esi_unique_orders"],2)

    def test_zero_remaining_esi_order_counted_as_excluded_not_region_failure(self):
        with tempfile.TemporaryDirectory() as td:
            fake=FakeApi()
            fake.exhausted_region=True
            record=fetch_region(fake,10000003,Path(td))
            self.assertEqual(record["status"],"EMPTY_MARKET_CONFIRMED")
            self.assertEqual(record["exhausted_orders_excluded"],1)
            self.assertEqual(record["orders"],0)

    def test_unrelated_invalid_order_has_explicit_field_and_order_id(self):
        with tempfile.TemporaryDirectory() as td:
            fake=FakeApi()
            fake.invalid_region=True
            record=fetch_region(fake,10000003,Path(td))
            self.assertEqual(record["status"],"FAILED")
            self.assertIn("ESI_ORDER_INVALID_VALUE:price",record["error"])
            self.assertIn("page=1:order_id=303",record["error"])

    def test_region_override_stays_partial_and_is_checked_against_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            report,_=run(root,fetcher=FakeApi(),fetch_reference=False,
                         region_ids_override=[10000001,10000003])
            self.assertEqual(report["status"],"PARTIAL_REGION_TEST_ONLY")
            self.assertEqual(report["attempted_regions"],2)
            self.assertFalse(report["full_universe_requested"])
            invalid,_=run(root,fetcher=FakeApi(),fetch_reference=False,
                          region_ids_override=[10000099])
            self.assertEqual(invalid["status"],"VALIDATION_FAILED")
            self.assertIn("REGION_OVERRIDE_NOT_IN_ESI_DIRECTORY",
                          invalid["error"])

    def test_active_order_range_and_minimum_are_retained_exactly(self):
        raw={**item(201),"min_volume":3,"range":"region"}
        saved=_row(raw,10000002)
        self.assertEqual(saved["min_volume"],3)
        self.assertEqual(saved["range"],"region")
        self.assertEqual(saved["volume_total"],5)
        with self.assertRaisesRegex(ValidationError,"MISSING_REQUIRED_FIELD"):
            _row({k:v for k,v in raw.items() if k!="range"},10000002)
        with self.assertRaisesRegex(ValidationError,"INVALID_VALUE:range"):
            _row({**raw,"range":"galaxy"},10000002)

    def test_http_last_modified_must_be_valid(self):
        self.assertEqual(_http_time(STAMP).tzinfo,timezone.utc)
        with self.assertRaises(ValidationError):
            _http_time(None)

    def test_two_complete_pages_atomic_archive(self):
        with tempfile.TemporaryDirectory() as td:
            fake=FakeApi()
            p=Path(td)
            report=fetch_region(fake,10000001,p)
            self.assertEqual(report["status"],"COMPLETE")
            self.assertEqual(report["orders"],2)
            self.assertEqual(report["pages"],2)
            import gzip
            with gzip.open(p/"10000001.jsonl.gz","rt",encoding="utf-8") as f:
                archived=json.loads(next(f))
            self.assertEqual(archived["min_volume"],1)
            self.assertEqual(archived["range"],"station")
            self.assertEqual(archived["volume_total"],5)
            self.assertTrue((p/"10000001.jsonl.gz").is_file())
            self.assertFalse((p/"10000001.jsonl.gz.part").exists())

    def test_pagination_last_modified_conflict_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            fake=FakeApi()
            fake.version_drift=True
            p=Path(td)
            with patch("v4.esi_parallel_validation.time.sleep"):
                report=fetch_region(fake,10000001,p)
            self.assertEqual(report["status"],"FAILED")
            self.assertIn("VERSION_MISMATCH",report["error"])
            self.assertFalse((p/"10000001.jsonl.gz").exists())

    def test_404_region_never_called_verified_empty(self):
        with tempfile.TemporaryDirectory() as td:
            report=fetch_region(FakeApi(),10000002,Path(td))
            self.assertEqual(report["status"],"MARKET_ENDPOINT_404_UNVERIFIED")
            self.assertFalse((Path(td)/"10000002.jsonl.gz").exists())

    def test_full_region_census_with_known_404_and_diff(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            src=install_ref(root)
            original=src.read_bytes()
            fake=FakeApi()
            report,out=run(root,fetcher=fake,max_workers=2)
            self.assertEqual(report["status"],
                             "PUBLIC_ESI_RETRIEVAL_COMPLETE_WITH_404_CAVEAT")
            self.assertEqual(report["attempted_regions"],3)
            self.assertEqual(report["esi_unique_orders"],3)
            self.assertEqual(report["esi_pages"],3)
            self.assertEqual(report["region_status_counts"]["COMPLETE"],2)
            self.assertEqual(report["unverified_404_regions"],[10000002])
            comparison=report["comparison"]
            self.assertEqual(comparison["matched_order_ids"],1)
            self.assertEqual(comparison["esi_only_order_ids"],2)
            self.assertEqual(comparison["everef_only_order_ids"],1)
            self.assertEqual(comparison["matched_price_changes"],1)
            self.assertEqual(comparison["matched_remaining_volume_changes"],1)
            self.assertEqual(comparison["jita_buy_order_count_esi"],3)
            self.assertEqual(comparison["jita_buy_order_count_everef"],2)
            self.assertEqual(comparison["reference_regions_not_complete_on_esi"],[])
            self.assertEqual(src.read_bytes(),original)
            self.assertTrue((out/"comparison.sqlite3").exists())
            self.assertTrue((out/"report.json").exists())
            self.assertFalse((root/"logs").exists())
            self.assertNotIn("mail_recipients",report)
            self.assertEqual(report["data_source_decision"],"DO_NOT_SWITCH_PRODUCTION")

    def test_incomplete_or_partial_full_census_never_claims_complete(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            fake=FakeApi()
            fake.fail_region=True
            report,_=run(root,fetcher=fake,fetch_reference=False)
            self.assertEqual(report["status"],"INCOMPLETE_ESI_REGIONS")
            self.assertEqual(report["failed_regions"],[10000002])
            self.assertEqual(report["data_source_decision"],"DO_NOT_SWITCH_PRODUCTION")
            short,_=run(root,fetcher=FakeApi(),max_regions=2,
                        fetch_reference=False)
            self.assertEqual(short["status"],"PARTIAL_REGION_TEST_ONLY")
            self.assertFalse(short["full_universe_requested"])
            self.assertEqual(short["attempted_regions"],2)

    def test_404_with_ref_region_is_not_coverage_success(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            source=install_ref(root)
            # Simulate a previously known market region becoming 404 in ESI.
            text=bz2.decompress(source.read_bytes()).decode()
            text=text.replace("10000001","10000002")
            source.write_bytes(bz2.compress(text.encode()))
            report,_=run(root,fetcher=FakeApi())
            self.assertEqual(report["status"],"PUBLIC_ESI_404_COVERAGE_UNVERIFIED")
            self.assertEqual(report["comparison"]["reference_regions_not_complete_on_esi"],
                             [10000002])

    def test_archived_esi_orders_can_be_reconciled_offline_without_redownload(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            source=install_ref(root)
            with bz2.open(source,"at",encoding="utf-8") as output:
                output.write("1001,10000001,60003760,34,7,0,True\n")
            original=source.read_bytes()
            fake=FakeApi()
            report,folder=run(root,fetcher=fake,fetch_reference=True)
            self.assertEqual(report["reference"]["excluded_nontradeable_orders"]
                             ["exhausted_zero_remaining"],1)
            first= (folder/"comparison.sqlite3").read_bytes()
            with patch("v4.esi_parallel_validation.Api") as no_network:
                result,saved=reconcile_saved(root,folder.name)
                no_network.assert_not_called()
            self.assertTrue(saved.is_file())
            self.assertTrue((folder/"reconciled.sqlite3").is_file())
            self.assertEqual((folder/"comparison.sqlite3").read_bytes(),first)
            self.assertEqual(source.read_bytes(),original)
            self.assertEqual(result["archived_esi_orders"],3)
            self.assertEqual(result["reference_tradeable_orders"],2)
            self.assertEqual(result["reference_excluded_nontradeable_orders"]
                             ["exhausted_zero_remaining"],1)
            self.assertEqual(result["data_source_decision"],"DO_NOT_SWITCH_PRODUCTION")
            with self.assertRaisesRegex(ValidationError,"ALREADY_EXISTS"):
                reconcile_saved(root,folder.name)

    def test_current_http_header_case_normalizes_and_respects_429(self):
        fake_response=Mock(status_code=200,headers={
            "X-Pages":"2","Last-Modified":STAMP})
        fake_response.json.return_value=[item(101)]
        api=Api(min_interval=0)
        fake_session=Mock()
        fake_session.get.return_value=fake_response
        api.local.session=fake_session
        code,data,headers=api.request("/markets/10000001/orders/",{"page":1})
        self.assertEqual(code,200)
        self.assertEqual(headers["x-pages"],"2")
        self.assertEqual(headers["last-modified"],STAMP)
        self.assertEqual(data[0]["order_id"],101)
        rate_limited=Mock(status_code=429,headers={"Retry-After":"1"})
        fake_session.get.side_effect=[rate_limited,fake_response]
        with patch("v4.esi_parallel_validation.time.sleep"):
            code,_,headers=api.request("/markets/10000001/orders/",{"page":1})
        self.assertEqual(code,200)
        self.assertEqual(api.counts["429"],1)


if __name__=="__main__":
    unittest.main()
