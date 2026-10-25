"""Tests for active-only V4 bounded hot SQLite proof retention."""
from __future__ import annotations
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from v4.local_store import _init
from v4.hot_retention import maintain, policy


class HotRetentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/"sqlite").mkdir()
        (self.root/"runs").mkdir()
        self.dbfile=self.root/"sqlite"/"v4-shadow.sqlite3"
        self.rows=[]

    def setup_ledger(self, *, mode="active"):
        with closing(sqlite3.connect(self.dbfile)) as db:
            db.execute("PRAGMA auto_vacuum=INCREMENTAL")
            _init(db)
            if mode!="legacy":
                db.execute(
                    "CREATE TABLE v4_hot_policy("
                    " singleton INTEGER PRIMARY KEY,policy_version INTEGER,"
                    " keep_runs INTEGER,active INTEGER)")
                db.execute(
                    "INSERT INTO v4_hot_policy VALUES (1,1,24,?)",
                    (1 if mode=="active" else 0,))
                db.execute(
                    "CREATE TABLE v4_cold_proofs("
                    "run_id TEXT PRIMARY KEY,archive_sha256 TEXT,"
                    "raw_sha256 TEXT,proof_count INTEGER,archived_at TEXT)")
            for i in range(26):
                rid=f"v4-retention-test-{i:03}"
                body=(json.dumps(
                    {"instance":f"market:{i:03}:001","reason":"TEST",
                     "status":"WATCH"})+"\n").encode()
                folder=self.root/"runs"/str(i)
                folder.mkdir()
                (folder/"all_proofs.jsonl").write_bytes(body)
                (folder/"deep_shadow.json").write_text(
                    json.dumps({"run_id":rid}),encoding="utf-8")
                sha=hashlib.sha256(body).hexdigest()
                db.execute("INSERT INTO scan_runs VALUES (?,?,?,?,?,?)",
                           (rid,"SHADOW_VERIFIED_OFFLINE",1,sha,"{}",
                            f"2026-10-{i+1:02}T00:00:00Z"))
                db.execute("INSERT INTO proof_versions VALUES (?,?,?,?,?)",
                           (rid,f"market:{i:03}:001","WATCH","TEST",
                            body.decode().strip()))
                self.rows.append(rid)
            db.commit()

    def count(self):
        with closing(sqlite3.connect(self.dbfile)) as db:
            return db.execute(
                "SELECT COUNT(*) FROM proof_versions").fetchone()[0]

    def test_legacy_database_never_mutates(self):
        self.setup_ledger(mode="legacy")
        result=maintain(self.root,apply=True)
        self.assertEqual(result["status"],"NOT_ENABLED")
        self.assertEqual(result["runs_pruned"],0)
        self.assertEqual(self.count(),26)

    def test_candidate_inactive_database_never_mutates(self):
        self.setup_ledger(mode="inactive")
        result=maintain(self.root,apply=True)
        self.assertEqual(result["status"],"NOT_ENABLED")
        self.assertEqual(policy(self.root)["status"],"STAGED_INACTIVE")
        self.assertEqual(self.count(),26)

    def test_two_expired_runs_archived_and_pruned_incrementally(self):
        self.setup_ledger(mode="active")
        self.assertEqual(policy(self.root)["status"],"ACTIVE")
        preview=maintain(self.root)
        self.assertEqual(preview["eligible_old_runs"],2)
        self.assertFalse(preview["sqlite_modified"])
        with patch("v4.proof_cold_archive.MIN_FREE_GIB",0):
            first=maintain(self.root,apply=True)
        self.assertEqual(first["status"],"PRUNED")
        self.assertEqual(first["proof_rows_pruned"],1)
        self.assertEqual(first["archived_new_runs"],1)
        self.assertEqual(self.count(),25)
        self.assertTrue((self.root/"cold-proof-archives"/
                         (self.rows[0]+".jsonl.gz")).exists())
        with patch("v4.proof_cold_archive.MIN_FREE_GIB",0):
            second=maintain(self.root,apply=True)
        self.assertEqual(second["runs_pruned"],1)
        self.assertEqual(self.count(),24)
        with closing(sqlite3.connect(self.dbfile)) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM scan_runs").fetchone()[0],26)
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM v4_cold_proofs").fetchone()[0],2)
            self.assertEqual(db.execute(
                "PRAGMA auto_vacuum").fetchone()[0],2)
            self.assertEqual(db.execute(
                "PRAGMA integrity_check").fetchone()[0],"ok")

    def test_incremental_vacuum_reclaims_multiple_pages_not_just_one(self):
        self.setup_ledger(mode="active")
        # A large old proof has overflow pages; the cold copy is updated
        # to preserve a valid byte-for-byte recovery source.
        body=(json.dumps({
            "instance":"market:000:001","reason":"TEST",
            "status":"WATCH","extra":"x"*500000})+"\\n").encode()
        (self.root/"runs"/"0"/"all_proofs.jsonl").write_bytes(body)
        with closing(sqlite3.connect(self.dbfile)) as db:
            db.execute("UPDATE scan_runs SET proof_sha256=? WHERE run_id=?",
                       (hashlib.sha256(body).hexdigest(),self.rows[0]))
            db.execute("UPDATE proof_versions SET proof_json=? WHERE run_id=?",
                       (body.decode().strip(),self.rows[0]))
            db.commit()
        with patch("v4.proof_cold_archive.MIN_FREE_GIB",0):
            result=maintain(self.root,apply=True,max_vacuum_pages=1000)
        self.assertEqual(result["runs_pruned"],1)
        self.assertGreater(result["vacuum_pages_reclaimed"],20)
        self.assertEqual(self.count(),25)

    def test_modified_raw_proof_blocks_prune(self):
        self.setup_ledger(mode="active")
        (self.root/"runs"/"0"/"all_proofs.jsonl").write_bytes(b"changed\n")
        with patch("v4.proof_cold_archive.MIN_FREE_GIB",0):
            with self.assertRaisesRegex(RuntimeError,"HASH_OR_COUNT_MISMATCH"):
                maintain(self.root,apply=True)
        self.assertEqual(self.count(),26)

    def test_read_only_inspection_does_not_create_cold_files(self):
        self.setup_ledger(mode="active")
        result=maintain(self.root)
        self.assertEqual(result["eligible_old_runs"],2)
        self.assertFalse((self.root/"cold-proof-archives").exists())

    def test_legacy_policy_malformed_is_disabled(self):
        self.setup_ledger(mode="active")
        with closing(sqlite3.connect(self.dbfile)) as db:
            db.execute("UPDATE v4_hot_policy SET keep_runs=1")
            db.commit()
        self.assertEqual(policy(self.root)["status"],"POLICY_INVALID")
        self.assertEqual(maintain(self.root,apply=True)["status"],"NOT_ENABLED")
        self.assertEqual(self.count(),26)

    def test_background_maintenance_errors_are_nonfatal_for_mail(self):
        from v4.local_service import post_scan_hot_retention
        with patch("v4.hot_retention.maintain",
                   side_effect=RuntimeError("simulated failure")):
            result=post_scan_hot_retention(self.root)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertTrue(result["scanner_and_mail_unchanged"])


if __name__=="__main__":
    unittest.main()
