import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from v3_market_alert_state import acknowledge, load, plan
from v3_scan_health import _inspect, channel_healthy


class MarketGmailStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "gmail_market_state.csv"
        self.t0 = datetime(2026, 10, 10, tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def c(self, ident=42, profit=70_000_000, roi=0.20):
        return {"id": ident, "profit": profit, "roi": roi}

    def test_baseline_no_backfill_and_no_duplicate(self):
        self.assertEqual(plan(self.path, [self.c()], now=self.t0), [])
        self.assertEqual(plan(self.path, [self.c()], now=self.t0 + timedelta(hours=7)), [])

    def test_reentry_after_cooldown(self):
        plan(self.path, [self.c()], now=self.t0)
        plan(self.path, [], now=self.t0 + timedelta(hours=1))
        self.assertEqual(plan(self.path, [self.c()], now=self.t0 + timedelta(hours=2)), [])
        pending = plan(self.path, [self.c()], now=self.t0 + timedelta(hours=7))
        self.assertEqual([x["id"] for x in pending], [42])
        acknowledge(self.path, pending[0], now=self.t0 + timedelta(hours=7))
        self.assertEqual(plan(self.path, [self.c()], now=self.t0 + timedelta(hours=14)), [])

    def test_material_change_and_retry_on_failed_send(self):
        plan(self.path, [self.c()], now=self.t0)
        improved = self.c(profit=96_000_000)
        self.assertEqual(plan(self.path, [improved], now=self.t0 + timedelta(hours=2)), [])
        pending = plan(self.path, [improved], now=self.t0 + timedelta(hours=7))
        self.assertEqual(len(pending), 1)
        # No acknowledge = SMTP failure: retry next scan, not permanently suppressed.
        self.assertEqual(len(plan(self.path, [improved], now=self.t0 + timedelta(hours=7, minutes=15))), 1)
        acknowledge(self.path, improved, now=self.t0 + timedelta(hours=7, minutes=15))
        self.assertEqual(plan(self.path, [improved], now=self.t0 + timedelta(hours=14)), [])
        self.assertEqual(load(self.path)[42]["pending"], "0")

    def test_new_market_type_after_baseline(self):
        plan(self.path, [self.c()], now=self.t0)
        self.assertEqual([c["id"] for c in plan(self.path, [self.c(), self.c(43)], now=self.t0 + timedelta(minutes=15))], [43])


class MarketScanHealthTests(unittest.TestCase):
    def test_empty_vs_failed_vs_missing(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "market.csv"
            p.write_text("\\n", encoding="utf-8")
            self.assertEqual(_inspect("success", p)["status"], "empty")
            self.assertEqual(_inspect("failure", p)["status"], "failed")
            p.unlink()
            self.assertEqual(_inspect("success", p)["status"], "missing_output")

    def test_unhealthy_lane_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "health.json"
            data = {
                "started_epoch": int(datetime.now(timezone.utc).timestamp()),
                "channels": {"v3-four-h-to-jita": {"status": "failed"}},
            }
            p.write_text(json.dumps(data), encoding="utf-8")
            with patch("v3_scan_health.HEALTH", p):
                self.assertFalse(channel_healthy("v3-four-h-to-jita", require_manifest=True))
                data["channels"]["v3-four-h-to-jita"]["status"] = "empty"
                p.write_text(json.dumps(data), encoding="utf-8")
                self.assertTrue(channel_healthy("v3-four-h-to-jita", require_manifest=True))
                data["started_epoch"] -= 4 * 3600
                p.write_text(json.dumps(data), encoding="utf-8")
                self.assertFalse(channel_healthy("v3-four-h-to-jita", require_manifest=True))


if __name__ == "__main__":
    unittest.main()
