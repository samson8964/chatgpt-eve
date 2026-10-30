"""Isolated WAL maintenance tests. Never reach installed Windows tasks or data."""
import hashlib
import json
import platform
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v4.local_store import _init
from v4.maintenance_checkpoint import ACK, checkpoint, inspect


class MaintenanceCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.host_os = platform.system()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "data"
        (self.root / "sqlite").mkdir(parents=True)
        self.db = self.root / "sqlite" / "v4-shadow.sqlite3"
        self.backup = Path(tmp.name) / "external-backup.sqlite3"
        with closing(sqlite3.connect(self.db)) as db:
            _init(db)  # Normal production WAL mode.
            self._append(db, "v4-checkpoint-000")
            self._append(db, "v4-checkpoint-001")
            db.commit()
        with closing(sqlite3.connect(self.db)) as source:
            with closing(sqlite3.connect(self.backup)) as copied:
                source.backup(copied)
                self.assertEqual(copied.execute(
                    "PRAGMA integrity_check").fetchone()[0], "ok")
                # The copied backup must be a standalone immutable file.
                if copied.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal":
                    copied.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                copied.execute("PRAGMA journal_mode=DELETE")
        self.assertTrue(self.backup.is_file())

    @staticmethod
    def _append(db, rid):
        raw = (json.dumps({"instance": "market:fixture:" + rid,
                           "status": "WATCH", "reason": "TEST"}) + "\n").encode()
        db.execute("INSERT INTO scan_runs VALUES (?,?,?,?,?,?)",
                   (rid, "SHADOW_VERIFIED_OFFLINE", 1,
                    hashlib.sha256(raw).hexdigest(), "{}",
                    "2026-10-26T00:00:00Z"))
        db.execute("INSERT INTO proof_versions VALUES (?,?,?,?,?)",
                   (rid, "market:fixture:" + rid, "WATCH", "TEST",
                    raw.decode().strip()))

    def _apply(self):
        # The fixture backup and production database are placed on one
        # tempfile volume. Simulate only the required separate-volume
        # condition here; real Windows enforcement has a separate test.
        with patch("v4.maintenance_checkpoint._check_tasks_disabled"), \
             patch("v4.hot_cutover.platform",
                   SimpleNamespace(system=lambda: "Linux")):
            # Replacing only the hot_cutover module binding must NOT alter
            # platform.system() as seen by local_run.exclusive_lock; Windows
            # must keep msvcrt and never attempt to import Linux fcntl.
            self.assertEqual(platform.system(), self.host_os)
            return checkpoint(
                self.root, external_backup=self.backup, acknowledgement=ACK)

    def test_default_inspection_does_not_modify_db(self):
        before = self.db.stat().st_size
        result = inspect(self.root)
        self.assertEqual(result["status"],
                         "READ_ONLY_WAL_CHECKPOINT_INSPECTION")
        self.assertFalse(result["checkpoint_performed"])
        self.assertFalse(result["source_modified"])
        self.assertEqual(self.db.stat().st_size, before)

    def test_mocked_hot_cutover_platform_keeps_real_lock_platform(self):
        # Regression for ModuleNotFoundError('fcntl') from patching the
        # shared platform.system function instead of the module binding.
        host = platform.system()
        with patch("v4.hot_cutover.platform",
                   SimpleNamespace(system=lambda: "Linux")):
            self.assertEqual(platform.system(), host)
            from v4 import local_run
            self.assertEqual(local_run.platform.system(), host)

    def test_verified_backup_allows_sqlite_controlled_checkpoint(self):
        output = self._apply()
        self.assertEqual(output["status"], "SOURCE_CHECKPOINTED_NO_CUTOVER")
        self.assertEqual(output["previous_journal_mode"], "wal")
        self.assertEqual(output["current_journal_mode"], "delete")
        self.assertEqual(output["scan_runs_unchanged"], 2)
        self.assertFalse(output["hot_cutover_performed"])
        for suffix in ("-wal", "-shm", "-journal"):
            self.assertFalse(Path(str(self.db) + suffix).exists())
        with closing(sqlite3.connect(self.db)) as live:
            self.assertEqual(live.execute(
                "PRAGMA journal_mode").fetchone()[0].lower(), "delete")
            self.assertEqual(live.execute(
                "SELECT COUNT(*) FROM proof_versions").fetchone()[0], 2)
        with closing(sqlite3.connect(self.backup)) as saved:
            self.assertEqual(saved.execute(
                "SELECT COUNT(*) FROM proof_versions").fetchone()[0], 2)

    def test_stale_backup_is_rejected_before_source_changes(self):
        with closing(sqlite3.connect(self.db)) as db:
            self._append(db, "v4-checkpoint-postbackup")
            db.commit()
        with self.assertRaisesRegex(
                RuntimeError, "EXTERNAL_BACKUP_INVALID_OR_STALE"):
            self._apply()
        with closing(sqlite3.connect(self.db)) as live:
            self.assertEqual(live.execute(
                "PRAGMA journal_mode").fetchone()[0].lower(), "wal")
            self.assertEqual(live.execute(
                "SELECT COUNT(*) FROM proof_versions").fetchone()[0], 3)

    def test_task_running_gate_fails_before_source_write(self):
        with patch("v4.maintenance_checkpoint._check_tasks_disabled",
                   side_effect=RuntimeError("TASK_STILL_ENABLED")):
            with self.assertRaisesRegex(RuntimeError, "TASK_STILL_ENABLED"):
                checkpoint(self.root, external_backup=self.backup,
                           acknowledgement=ACK)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute(
                "PRAGMA journal_mode").fetchone()[0].lower(), "wal")

    def test_wrong_ack_rejected_before_source_write(self):
        with self.assertRaisesRegex(RuntimeError, "CHECKPOINT_ACK_REQUIRED"):
            checkpoint(self.root, external_backup=self.backup,
                       acknowledgement="NO")
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute(
                "PRAGMA journal_mode").fetchone()[0].lower(), "wal")

    def test_rollback_journal_file_rejected_without_unlink(self):
        journal = Path(str(self.db) + "-journal")
        journal.write_bytes(b"leave-alone")
        try:
            with patch("v4.maintenance_checkpoint._check_tasks_disabled"):
                with self.assertRaisesRegex(
                        RuntimeError, "ROLLBACK_JOURNAL_PRESENT_DO_NOT_TOUCH"):
                    checkpoint(self.root, external_backup=self.backup,
                               acknowledgement=ACK)
            self.assertEqual(journal.read_bytes(), b"leave-alone")
        finally:
            # Fixture-owned sentinel only; never clean real SQLite sidecars.
            journal.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
