"""Offline official ESI regional daily trade-history reference cache tests."""
from __future__ import annotations
import bz2
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from v4.forge_history_reference import (
    CACHE, BASIS, FORGE_REGION_ID, _parse_day, load, refresh
)


def daily_blob(day, *, typ=34, avg=123.0, region=FORGE_REGION_ID,
               volume=18):
    value = ("date,region_id,type_id,average,highest,lowest,volume,order_count\n"
             f"{day},{region},{typ},{avg},{avg},{avg},{volume},2\n")
    return bz2.compress(value.encode())


class ForgeHistoryReferenceTests(unittest.TestCase):
    TODAY = date(2026, 11, 11)

    def test_latest_executed_day_average_and_region_only(self):
        with tempfile.TemporaryDirectory() as td:
            # Two historical days: newest wins. Cache must not invent
            # Jita 4-4 station execution or a single last transaction.
            def fetch(url):
                datepart = url.rsplit("market-history-", 1)[-1][:10]
                return daily_blob(datepart, avg=150.0 if
                                  datepart == "2026-11-10" else 100.0)
            result = refresh(Path(td), days=5, today=self.TODAY, fetch=fetch)
            self.assertEqual(result["days_available"], 5)
            quotes = load(Path(td), now=self.TODAY)
            self.assertEqual(quotes[34]["price"], 150.0)
            self.assertEqual(quotes[34]["date"], "2026-11-10")
            self.assertEqual(quotes[34]["basis"], BASIS)
            self.assertEqual(quotes[34]["region_id"], FORGE_REGION_ID)

    def test_missing_stale_invalid_cache_returns_no_reference(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self.assertEqual(load(root,now=self.TODAY),{})
            path=root/CACHE
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({
                "schema":1,"region_id":FORGE_REGION_ID,
                "source":"EVE_REF_ARCHIVE_ESI_FORGE_REGIONAL_DAILY_TRADE_AVERAGE",
                "built_on":"2026-11-01","quotes":{"34":{
                    "price":10,"date":"2026-10-31","volume":10}}}))
            self.assertEqual(load(root,now=self.TODAY),{})
            self.assertEqual(load(root,now=date(2026,11,7)),{})

    def test_non_forge_rows_not_considered_last_jita_trades(self):
        day=date(2026,11,10)
        self.assertFalse(_parse_day(daily_blob(day,region=10000043),day))
        with self.assertRaisesRegex(ValueError,"DATE_MISMATCH"):
            _parse_day(daily_blob(date(2026,11,9)),day)

    def test_incremental_preserves_old_rare_item_and_refreshes_recent_price(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            day1 = date(2026, 11, 10)
            def initial(url):
                trading_day = url.rsplit("market-history-",1)[-1][:10]
                base = ("date,region_id,type_id,average,highest,lowest,volume,order_count\n"
                        + trading_day + ",10000002,34,100,100,100,5,2\n")
                if trading_day == "2026-11-01":
                    base += trading_day + ",10000002,99,500,500,500,1,1\n"
                return bz2.compress(base.encode())
            refresh(root, days=10, today=self.TODAY, fetch=initial)
            def update(url):
                trading_day = url.rsplit("market-history-",1)[-1][:10]
                return daily_blob(trading_day,typ=34,avg=250)
            result = refresh(root, days=5, today=self.TODAY,
                             fetch=update, merge_existing=True)
            self.assertEqual(result["refresh_mode"], "INCREMENTAL_5_DAY_MERGE")
            quotes = load(root, now=self.TODAY)
            self.assertEqual(quotes[34]["price"],250)
            self.assertEqual(quotes[99]["price"],500)
            self.assertEqual(quotes[99]["date"],"2026-11-01")

    def test_resumable_bootstrap_reuses_valid_daily_files_after_interrupt(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            seen = []
            def download(url):
                seen.append(url)
                trading_day = url.rsplit("market-history-", 1)[-1][:10]
                return daily_blob(trading_day, avg=123.0)
            initial = refresh(root, days=5, today=self.TODAY, fetch=download,
                              workers=2, resume_archives=True)
            self.assertEqual(len(seen), 5)
            self.assertEqual(initial["days_available"], 5)
            seen.clear()
            repeated = refresh(root, days=5, today=self.TODAY, fetch=download,
                               workers=2, resume_archives=True)
            self.assertEqual(len(seen), 0)
            self.assertEqual(repeated["days_available"], 5)
            cached = root / "reference" / "forge-history-bootstrap-archives"
            broken = cached / "market-history-2026-11-10.csv.bz2"
            broken.write_bytes(b"invalid bzip2")
            seen.clear()
            refreshed = refresh(root, days=5, today=self.TODAY, fetch=download,
                                workers=2, resume_archives=True)
            self.assertEqual(len(seen), 1)
            self.assertEqual(refreshed["days_available"], 5)

    def test_daily_incremental_handles_two_unpublished_archives(self):
        from unittest.mock import Mock, patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            def initial(url):
                day = url.rsplit("market-history-", 1)[-1][:10]
                return daily_blob(day)
            refresh(root, days=5, today=self.TODAY, fetch=initial)
            def late_publisher(url, **kwargs):
                day = url.rsplit("market-history-", 1)[-1][:10]
                if day in {"2026-11-10", "2026-11-09"}:
                    return Mock(status_code=404)
                return Mock(status_code=200, content=daily_blob(day, avg=200))
            with patch("v4.forge_history_reference.requests.get",
                       side_effect=late_publisher):
                outcome = refresh(root, days=5, today=self.TODAY,
                                  workers=2, merge_existing=True)
            self.assertEqual(outcome["days_available"], 3)
            # A valid older quote survives a lagged publisher.
            self.assertEqual(load(root, now=self.TODAY)[34]["date"],
                             "2026-11-10")

    def test_incremental_refuses_missing_base_without_network(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,"INITIAL_FULL_REFRESH_REQUIRED"):
                refresh(Path(td), days=5, today=self.TODAY,
                        fetch=lambda url: self.fail("should not download"),
                        merge_existing=True)

    def test_publisher_incomplete_does_not_publish_new_cache(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            def fetch(url):
                return daily_blob("2026-11-01")
            with self.assertRaisesRegex(ValueError,"DATE_MISMATCH"):
                refresh(root,days=4,today=self.TODAY,fetch=fetch)
            self.assertFalse((root/CACHE).exists())


if __name__ == "__main__":
    unittest.main()
