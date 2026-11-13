"""Offline-only audit tests. All SQLite files live inside temp dirs."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from v4.cutover_verification import verify
from v4.local_store import _init


class PostCutoverVerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "sqlite").mkdir()
        self.db = self.root / "sqlite" / "v4-shadow.sqlite3"
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("PRAGMA auto_vacuum=INCREMENTAL")
            _init(db)
            db.execute(
                "CREATE TABLE v4_hot_policy (singleton INTEGER PRIMARY KEY,"
                "policy_version INTEGER,keep_runs INTEGER,active INTEGER)")
            db.execute("INSERT INTO v4_hot_policy VALUES (1,1,72,1)")
            db.execute(
                "CREATE TABLE v4_cold_proofs (run_id TEXT PRIMARY KEY,"
                "archive_sha256 TEXT,raw_sha256 TEXT,proof_count INTEGER,"
                "archived_at TEXT)")
            for i in range(75):
                rid = "cutover-fixture-%03d" % i
                db.execute("INSERT INTO scan_runs VALUES (?,?,?,?,?,?)",
                           (rid, "SHADOW_VERIFIED_OFFLINE", 1, "sha", "{}",
                            "2026-10-27T%02d:%02d:00Z" % (i // 60, i % 60)))
                if i >= 3:
                    db.execute("INSERT INTO proof_versions VALUES (?,?,?,?,?)",
                               (rid, "market:%03d" % i, "WATCH", "TEST", "{}"))
                else:
                    db.execute("INSERT INTO v4_cold_proofs VALUES (?,?,?,?,?)",
                               (rid, "archive-sha", "sha", 1, "2026-10-27"))
            db.commit()

    def test_activated_72_hot_3_cold_is_verified(self):
        result = verify(self.root)
        self.assertEqual(result["status"],
                         "CUTOVER_72_RUN_POLICY_VERIFIED_READ_ONLY")
        self.assertEqual(result["hot_proof_rows"], 72)
        self.assertEqual(result["detailed_hot_runs"], 72)
        self.assertEqual(result["cold_indexed_runs"], 3)
        self.assertFalse(result["mail_verified"])

    def test_inactive_hot_policy_is_rejected(self):
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("UPDATE v4_hot_policy SET active=0")
            db.commit()
        with self.assertRaisesRegex(RuntimeError, "NOT_ACTIVE"):
            verify(self.root)

    def test_missing_cold_index_is_rejected(self):
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("DELETE FROM v4_cold_proofs WHERE run_id=?",
                       ("cutover-fixture-000",))
            db.commit()
        with self.assertRaisesRegex(RuntimeError, "COLD_RUN_NOT_INDEXED"):
            verify(self.root)

    def test_missing_hot_proof_is_rejected(self):
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("DELETE FROM proof_versions WHERE run_id=?",
                       ("cutover-fixture-074",))
            db.commit()
        with self.assertRaisesRegex(RuntimeError, "HOT_RUN_PROOF_MISMATCH"):
            verify(self.root)

    def test_extra_cold_proof_is_rejected(self):
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("INSERT INTO proof_versions VALUES (?,?,?,?,?)",
                       ("cutover-fixture-000", "market:cold", "WATCH",
                        "TEST", "{}"))
            db.commit()
        with self.assertRaisesRegex(RuntimeError, "COLD_RUN_REMAINS"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main()
