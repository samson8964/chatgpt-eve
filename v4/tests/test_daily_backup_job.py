"""Isolated tests for out-of-band daily SQLite backups; no real DB copied."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from v4.daily_backup_job import perform


class DailyBackupJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "sqlite").mkdir()
        self.source = self.root / "sqlite" / "v4-shadow.sqlite3"
        self.source.write_bytes(b"fixture-source")

    def test_no_copy_when_not_due(self):
        with patch("v4.daily_backup_job.backup_due", return_value=False):
            out = perform(
                self.root,
                backup_fn=lambda root: self.fail("unexpected copy"),
                rotate_fn=lambda *args, **kw: self.fail("unexpected rotate"),
            )
        self.assertEqual(out["status"], "NOT_DUE")

    def test_due_starts_independent_backup_and_safe_rotation(self):
        calls = []
        path = self.root / "backups" / "verified.sqlite3"
        with patch("v4.daily_backup_job.backup_due", return_value=True), \
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
        with patch("v4.daily_backup_job.backup_due", return_value=True), \
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
        with patch("v4.daily_backup_job.backup_due", return_value=True), \
             patch("v4.daily_backup_job.REQUIRED_FREE_SLACK_GIB", 999999):
            out = perform(self.root, backup_fn=lambda _: self.fail("copy called"))
        self.assertEqual(out["status"], "BLOCKED_INSUFFICIENT_SPACE")

    def test_retention_failure_preserves_new_backup_and_reports_blocked(self):
        with patch("v4.daily_backup_job.backup_due", return_value=True), \
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
