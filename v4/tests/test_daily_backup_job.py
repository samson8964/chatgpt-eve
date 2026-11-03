"""Isolated tests for out-of-band daily SQLite backups; no real DB copied."""
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from v4.daily_backup_job import perform, scheduled_day_due


class DailyBackupJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "sqlite").mkdir()
        self.source = self.root / "sqlite" / "v4-shadow.sqlite3"
        self.source.write_bytes(b"fixture-source")

    def test_previous_local_date_is_due_even_if_less_than_24h(self):
        now = datetime.now().astimezone().replace(
            hour=3, minute=45, second=0, microsecond=0)
        prior = now - timedelta(hours=18)
        backup = self.root / "backups" / "v4-shadow-20261029T010000Z.sqlite3"
        backup.parent.mkdir()
        backup.write_bytes(b"fixture")
        import os
        os.utime(backup, (prior.timestamp(), prior.timestamp()))
        self.assertLess((now - prior).total_seconds(), 86400)
        self.assertTrue(scheduled_day_due(self.root, now))

    def test_same_local_calendar_date_skips_second_backup(self):
        now = datetime.now().astimezone().replace(
            hour=18, minute=0, second=0, microsecond=0)
        earlier = now - timedelta(hours=8)
        backup = self.root / "backups" / "v4-shadow-20261029T010000Z.sqlite3"
        backup.parent.mkdir()
        backup.write_bytes(b"fixture")
        import os
        os.utime(backup, (earlier.timestamp(), earlier.timestamp()))
        self.assertFalse(scheduled_day_due(self.root, now))

    def test_no_copy_when_not_due(self):
        with patch("v4.daily_backup_job.scheduled_day_due", return_value=False):
            out = perform(
                self.root,
                backup_fn=lambda root: self.fail("unexpected copy"),
                rotate_fn=lambda *args, **kw: self.fail("unexpected rotate"),
            )
        self.assertEqual(out["status"], "NOT_DUE")

    def test_due_starts_independent_backup_and_safe_rotation(self):
        calls = []
        path = self.root / "backups" / "verified.sqlite3"
        with patch("v4.daily_backup_job.scheduled_day_due", return_value=True), \
             patch("v4.daily_backup_job.REQUIRED_FREE_SLACK_GIB", 0):
            out = perform(
                self.root,
                backup_fn=lambda root: (
                    calls.append("copy") or
                    {"ok": True, "sqlite_integrity": "ok",
                     "path": str(path), "scan_runs": 3,
                     "proof_versions": 20}
                ),
                rotate_fn=lambda root, apply, expected_newest: (
                    calls.append("rotate") or
                    {"status": "ROTATED", "deleted": 2}
                ),
            )
        self.assertEqual(calls, ["copy", "rotate"])
        self.assertEqual(out["status"], "DAILY_BACKUP_VERIFIED")
        self.assertEqual(out["backup_retention"]["status"], "ROTATED")

    def test_no_rotation_if_backup_not_fully_validated(self):
        with patch("v4.daily_backup_job.scheduled_day_due", return_value=True), \
             patch("v4.daily_backup_job.REQUIRED_FREE_SLACK_GIB", 0):
            with self.assertRaisesRegex(RuntimeError, "NOT_VERIFIED"):
                perform(
                    self.root,
                    backup_fn=lambda root: {
                        "ok": True, "sqlite_integrity": "quick_check_ok",
                        "path": "unverified.sqlite3",
                    },
                    rotate_fn=lambda *args, **kw: self.fail("unexpected rotate"),
                )

    def test_low_disk_refuses_to_create_copy(self):
        with patch("v4.daily_backup_job.scheduled_day_due", return_value=True), \
             patch("v4.daily_backup_job.REQUIRED_FREE_SLACK_GIB", 999999):
            out = perform(self.root, backup_fn=lambda _: self.fail("copy called"))
        self.assertEqual(out["status"], "BLOCKED_INSUFFICIENT_SPACE")

    def test_retention_failure_preserves_new_backup_and_reports_blocked(self):
        with patch("v4.daily_backup_job.scheduled_day_due", return_value=True), \
             patch("v4.daily_backup_job.REQUIRED_FREE_SLACK_GIB", 0):
            out = perform(
                self.root,
                backup_fn=lambda root: {
                    "ok": True, "sqlite_integrity": "ok",
                    "path": str(self.root / "backups" / "verified.sqlite3")
                },
                rotate_fn=lambda *args, **kwargs: 1 / 0,
            )
        self.assertEqual(out["status"], "DAILY_BACKUP_VERIFIED")
        self.assertEqual(out["backup_retention"]["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
