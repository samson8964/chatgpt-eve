"""External V4 full backup fixture tests; no real scheduled tasks or user data."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from v4.external_backup import create, inspect, require_different_volume
from v4.local_store import _init
from v4.hot_cutover import _no_uncheckpointed_sidecars


class ExternalBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "production"
        (self.root / "sqlite").mkdir(parents=True)
        self.destination = Path(self.tmp.name) / "external"
        self.db = self.root / "sqlite" / "v4-shadow.sqlite3"
        with closing(sqlite3.connect(self.db)) as conn:
            _init(conn)
            for i in range(3):
                rid = f"test-external-{i}"
                raw = (json.dumps({"instance": f"market:test:{i}",
                                   "status": "WATCH", "reason": "TEST"}) + "\n").encode()
                conn.execute("INSERT INTO scan_runs VALUES (?,?,?,?,?,?)",
                             (rid, "SHADOW_VERIFIED_OFFLINE", 1,
                              hashlib.sha256(raw).hexdigest(), "{}",
                              f"2026-10-2{i}T00:00:00Z"))
                conn.execute("INSERT INTO proof_versions VALUES (?,?,?,?,?)",
                             (rid, f"market:test:{i}", "WATCH", "TEST",
                              raw.decode().strip()))
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            mode = conn.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
            self.assertEqual(mode.lower(), "delete")

    def _create(self):
        # Test fixtures put source and simulated external backup inside one
        # TemporaryDirectory, hence on the SAME Windows volume. Bypass only
        # this fixture-inapplicable gate. Its real Windows enforcement is
        # separately tested below; production code is unchanged.
        with patch("v4.external_backup._check_tasks_disabled"), \
             patch("v4.external_backup.require_different_volume"), \
             patch("v4.external_backup.MIN_SLACK_GIB", 0):
            return create(self.root, self.destination,
                          now=datetime(2026, 10, 26, 11, tzinfo=timezone.utc))

    def test_read_only_does_not_create_destination(self):
        with patch("v4.external_backup.require_different_volume"):
            result = inspect(self.root, self.destination)
        self.assertEqual(result["status"],
                         "READ_ONLY_EXTERNAL_BACKUP_INSPECTION")
        self.assertFalse(result["created"])
        self.assertFalse(self.destination.exists())

    def test_full_backup_validated_without_source_mutation(self):
        old = self.db.read_bytes()
        result = self._create()
        self.assertEqual(result["status"], "FULL_EXTERNAL_BACKUP_VERIFIED")
        self.assertTrue(Path(result["path"]).is_file())
        self.assertEqual(result["scan_runs"], 3)
        self.assertEqual(result["proof_rows"], 3)
        self.assertEqual(old, self.db.read_bytes())
        with closing(sqlite3.connect(result["path"])) as dest:
            self.assertEqual(dest.execute(
                "PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertFalse(Path(str(result["path"]) + ".part").exists())

    def test_committed_wal_is_included_in_backup_but_blocks_cutover(self):
        # A real WAL with committed rows is different from random bytes
        # masquerading as a -wal file. Keep a connection open so both
        # SQLite sidecars remain present during the online backup.
        with closing(sqlite3.connect(self.db)) as writer:
            self.assertEqual(writer.execute(
                "PRAGMA journal_mode=WAL").fetchone()[0].lower(), "wal")
            rid = "test-external-wal"
            raw = (json.dumps({"instance": "market:test:wal",
                               "status": "WATCH", "reason": "TEST"}).encode() + bytes([10]))
            writer.execute("INSERT INTO scan_runs VALUES (?,?,?,?,?,?)",
                           (rid, "SHADOW_VERIFIED_OFFLINE", 1,
                            hashlib.sha256(raw).hexdigest(), "{}",
                            "2026-10-26T01:00:00Z"))
            writer.execute("INSERT INTO proof_versions VALUES (?,?,?,?,?)",
                           (rid, "market:test:wal", "WATCH", "TEST",
                            raw.decode().strip()))
            writer.commit()
            wal = self.db.with_name(self.db.name + "-wal")
            self.assertTrue(wal.exists())
            with self.assertRaisesRegex(
                    RuntimeError, "SQLITE_JOURNAL_PRESENT_CLOSE_ALL_V4_READERS"):
                _no_uncheckpointed_sidecars(self.db)
            result = self._create()
            self.assertEqual(result["status"], "FULL_EXTERNAL_BACKUP_VERIFIED")
            self.assertEqual(result["scan_runs"], 4)
            self.assertEqual(result["proof_rows"], 4)
            with closing(sqlite3.connect(result["path"])) as copy:
                self.assertEqual(copy.execute(
                    "PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(copy.execute(
                    "SELECT COUNT(*) FROM scan_runs").fetchone()[0], 4)
            self.assertTrue(wal.exists())

    def test_refuses_overwrite_of_existing_snapshot(self):
        self._create()
        with self.assertRaisesRegex(FileExistsError,
                                    "EXTERNAL_BACKUP_TARGET_EXISTS"):
            self._create()

    def test_cross_volume_windows_gate(self):
        with patch("v4.external_backup.platform.system",
                   return_value="Windows"):
            require_different_volume(Path(r"C:\V4"), Path(r"D:\backup"))
            with self.assertRaisesRegex(RuntimeError, "OTHER_VOLUME"):
                require_different_volume(Path(r"C:\V4"),
                                         Path(r"C:\backup"))

    def test_real_windows_inspect_rejects_same_volume(self):
        # Unlike algorithm fixtures, this invokes the REAL guard, exercising
        # the same-volume rejection reached by the user's original test run.
        with patch("v4.external_backup.platform.system",
                   return_value="Windows"):
            with self.assertRaisesRegex(RuntimeError, "OTHER_VOLUME"):
                inspect(self.root, self.destination)
        self.assertFalse(self.destination.exists())

    def test_create_refuses_live_tasks(self):
        with patch("v4.external_backup._check_tasks_disabled",
                   side_effect=RuntimeError("TASK_NOT_DISABLED")), \
             patch("v4.external_backup.require_different_volume"), \
             patch("v4.external_backup.MIN_SLACK_GIB", 0):
            with self.assertRaisesRegex(RuntimeError, "TASK_NOT_DISABLED"):
                create(self.root, self.destination)
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
