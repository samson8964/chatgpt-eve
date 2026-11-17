"""Isolated V4 disk governor, no user data or internet access."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from v4.storage_governor import GIB, HISTORY_LIMIT, record, report
from v4.storage_alert import send_capacity_alert


class StorageGovernorTests(unittest.TestCase):
    def test_inventory_classifies_protected_history_without_deletion(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = root / "runs" / "20261026" / "source"
            raw.mkdir(parents=True)
            file = raw / "market_orders.csv.bz2"
            file.write_bytes(b"historical-evidence")
            (root / "sqlite").mkdir()
            (root / "sqlite" / "v4-shadow.sqlite3").write_bytes(b"db-evidence")
            result = report(root, free_bytes=100 * GIB)
            self.assertEqual(result["inventory_status"], "COMPLETE")
            self.assertEqual(result["severity"], "OK")
            self.assertEqual(result["files_deleted"], 0)
            self.assertFalse(result["database_modified"])
            self.assertFalse(result["automatic_raw_snapshot_deletion_enabled"])
            self.assertEqual(result["project_file_count"], 2)
            self.assertEqual(file.read_bytes(), b"historical-evidence")

    def test_disk_threshold_and_warning(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertEqual(report(root, free_bytes=19 * GIB)["severity"], "STOP")
            self.assertEqual(report(root, free_bytes=20 * GIB)["severity"], "WARNING")
            self.assertEqual(report(root, free_bytes=41 * GIB)["severity"], "OK")

    def test_growing_disk_consumption_warns_in_advance(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            now = datetime(2026, 10, 26, 10, tzinfo=timezone.utc)
            old = record(root, free_bytes=70 * GIB,
                         now=now - timedelta(days=1))
            self.assertTrue(old["history_recorded"])
            new = record(root, free_bytes=50 * GIB, now=now)
            self.assertEqual(new["severity"], "WARNING")
            self.assertAlmostEqual(
                new["growth"]["daily_free_gib_change"], -20.0, places=1)
            self.assertAlmostEqual(
                new["growth"]["days_until_20_gib"], 1.5, places=1)
            self.assertTrue(new["history_recorded"])
            again = record(root, free_bytes=50 * GIB, now=now)
            self.assertFalse(again["history_recorded"])

    def test_history_is_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "logs"
            p.mkdir()
            samples = [
                {"time": (datetime(2026, 10, 1, tzinfo=timezone.utc)
                          + timedelta(hours=i)).isoformat(),
                 "free_bytes": (60 + i) * GIB}
                for i in range(HISTORY_LIMIT + 20)]
            (p / "storage-capacity-history.json").write_text(
                json.dumps({"schema": 1, "samples": samples}), encoding="utf-8")
            result = record(root, free_bytes=80 * GIB,
                            now=datetime(2026, 11, 1, tzinfo=timezone.utc))
            self.assertTrue(result["history_recorded"])
            doc = json.loads(
                (p / "storage-capacity-history.json").read_text("utf-8"))
            self.assertEqual(len(doc["samples"]), HISTORY_LIMIT)

    def test_incomplete_inventory_does_not_claim_healthy(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("v4.storage_governor._files",
                       return_value={"total_bytes": 0, "files": 1,
                                     "categories": {},
                                     "status": "FILE_LIMIT_EXCEEDED"}):
                result = report(Path(td), free_bytes=100 * GIB)
            self.assertEqual(result["severity"], "UNKNOWN")

    def test_alert_dedup_warning_then_stop_and_no_trade_mail(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stamp = datetime(2026, 10, 26, 11, tzinfo=timezone.utc)
            config = {"sender": "sender@gmail.com",
                      "recipient": "owner@gmail.com"}
            sends = []
            def record_email(msg, sender, secret, smtp_factory=None):
                self.assertIn("磁盘", msg["Subject"])
                self.assertNotIn("V4捡漏待核", msg["Subject"])
                sends.append(msg)
            with patch("v4.research_mail._config", return_value=config), \
                 patch("v4.research_mail._windows_keyring",
                       return_value=Mock(get_password=lambda *_: "mock-secret")), \
                 patch("v4.research_mail._send_review_smtp",
                       side_effect=record_email):
                payload = {"severity": "WARNING", "free_gib": 25.0,
                           "growth": {"daily_free_gib_change": -3}}
                first = send_capacity_alert(root, payload, now=stamp)
                second = send_capacity_alert(root, payload, now=stamp)
                stopped = send_capacity_alert(
                    root, {**payload, "severity": "STOP"}, now=stamp)
            self.assertTrue(first["sent"])
            self.assertFalse(second["sent"])
            self.assertEqual(second["status"],
                             "CAPACITY_ALERT_ALREADY_SENT_TODAY")
            self.assertTrue(stopped["sent"])
            self.assertEqual(len(sends), 2)

    def test_alert_is_inert_when_healthy(self):
        with tempfile.TemporaryDirectory() as td:
            r = send_capacity_alert(Path(td), {"severity": "OK"})
            self.assertFalse(r["sent"])
            self.assertFalse((Path(td) / "logs").exists())


if __name__ == "__main__":
    unittest.main()
