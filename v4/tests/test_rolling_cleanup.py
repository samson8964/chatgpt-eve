"""End-to-end tests for opt-in rolling cleanup: SQL, raw files and crash replay."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from v4 import rolling_cleanup as mod


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "runs").mkdir()
        (self.root / "sqlite").mkdir()
        (self.root / "config").mkdir()
        self.db_path = self.root / "sqlite" / "v4-shadow.sqlite3"
        with closing(sqlite3.connect(self.db_path)) as db:
            db.execute("CREATE TABLE scan_runs (run_id TEXT PRIMARY KEY,"
                       "status TEXT,proof_count INTEGER,proof_sha256 TEXT,"
                       "report_json TEXT,audited_at TEXT)")
            db.execute("CREATE TABLE proof_versions ("
                       "run_id TEXT,instance TEXT,proof_json TEXT)")
            db.commit()

    def add(self, i, *, complete=True):
        name = "20261028T%06dZ-%08x" % (i, i)
        run_id = "run-%04d" % i
        folder = self.root / "runs" / name
        folder.mkdir()
        (folder / "source").mkdir()
        (folder / "source" / "market.csv.bz2").write_bytes(b"market")
        (folder / "deep_shadow.json").write_text(json.dumps({"run_id": run_id}))
        (folder / "manifest.json").write_text(json.dumps({
            "status": "SHADOW_RECORDED" if complete else "FAILED",
            "coverage_gate": mod._complete.__globals__["GOOD_COVERAGE"],
            "source_input_integrity": "ALL_PARSED",
            "failed_structure_lanes": {},
            "proofs_sha256": "hash",
            "sqlite_unique_proofs": 1,
        }))
        with closing(sqlite3.connect(self.db_path)) as db:
            db.execute("INSERT INTO scan_runs VALUES (?,?,?,?,?,?)",
                       (run_id, mod.GOOD_STATUS, 1, "hash", "{}",
                        "%06d" % i))
            db.execute("INSERT INTO proof_versions VALUES (?,?,?)",
                       (run_id, "instance", "{}"))
            db.commit()
        return folder

    def add_many(self, n=73):
        for i in range(n):
            self.add(i)

    def sql_counts(self):
        with closing(sqlite3.connect(self.db_path)) as db:
            return (
                db.execute("SELECT COUNT(*) FROM scan_runs").fetchone()[0],
                db.execute("SELECT COUNT(*) FROM proof_versions").fetchone()[0],
            )

    def test_default_is_read_only_and_inactive(self):
        self.add_many()
        before = self.sql_counts()
        result = mod.cleanup(self.root)
        self.assertEqual(result["old_run_count"], 1)
        self.assertFalse(result["activated"])
        self.assertEqual(self.sql_counts(), before)
        self.assertTrue((self.root / "runs" / "20261028T000000Z-00000000").exists())

    def test_apply_without_activation_is_rejected(self):
        self.add_many()
        with self.assertRaisesRegex(RuntimeError, "NOT_ACTIVATED"):
            mod.cleanup(self.root, apply=True)
        self.assertEqual(self.sql_counts(), (73, 73))

    def test_72_exactly_does_not_remove_anything(self):
        self.add_many(72)
        with patch.object(mod, "_require_activation"):
            out = mod.cleanup(self.root, apply=True)
        self.assertEqual(out["deleted"], 0)
        self.assertEqual(self.sql_counts(), (72, 72))

    def test_73rd_deletes_first_from_sql_and_disk(self):
        first = self.add(0)
        for i in range(1, 73):
            self.add(i)
        with patch.object(mod, "_require_activation"):
            out = mod.cleanup(self.root, apply=True)
        self.assertEqual(out["deleted"], 1)
        self.assertEqual(out["raw_folders_deleted"], 1)
        self.assertFalse(first.exists())
        self.assertEqual(self.sql_counts(), (72, 72))

    def test_74th_deletes_two_and_stops_at_72(self):
        self.add_many(74)
        with patch.object(mod, "_require_activation"):
            out = mod.cleanup(self.root, apply=True)
        self.assertEqual(out["deleted"], 2)
        self.assertEqual(self.sql_counts(), (72, 72))

    def test_unconfirmed_mail_pins_old_run(self):
        self.add_many()
        with patch.object(mod, "_require_activation"), patch.object(
                mod, "_mail_guards", return_value=["GMAIL_UNCONFIRMED"]):
            out = mod.cleanup(self.root, apply=True)
        self.assertEqual(out["blocked"], 1)
        self.assertEqual(self.sql_counts(), (73, 73))

    def test_crash_after_sql_commit_replays_pending_folder_removal(self):
        first = self.add(0)
        for i in range(1, 73):
            self.add(i)
        with patch.object(mod, "_require_activation"), patch.object(
                mod.shutil, "rmtree", side_effect=OSError("simulated crash")):
            with self.assertRaisesRegex(OSError, "simulated crash"):
                mod.cleanup(self.root, apply=True)
        self.assertTrue(first.exists())
        self.assertEqual(self.sql_counts(), (72, 72))
        with closing(sqlite3.connect(self.db_path)) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM rolling72_pending").fetchone()[0], 1)
        with patch.object(mod, "_require_activation"):
            again = mod.cleanup(self.root, apply=True)
        self.assertEqual(again["raw_folders_deleted"], 1)
        self.assertFalse(first.exists())
        self.assertEqual(self.sql_counts(), (72, 72))

    def test_failed_run_never_counts_or_deletes(self):
        self.add_many(72)
        self.add(72, complete=False)
        with patch.object(mod, "_require_activation"):
            result = mod.cleanup(self.root, apply=True)
        self.assertEqual(result["deleted"], 0)
        self.assertEqual(self.sql_counts(), (73, 73))

    def test_expired_cold_archive_and_receipts_are_reclaimed(self):
        first = self.add(0)
        for i in range(1, 73):
            self.add(i)
        cold = self.root / "cold-proof-archives"
        cold.mkdir()
        archive = cold / "run-0000.jsonl.gz"
        manifest = cold / "run-0000.manifest.json"
        archive.write_bytes(b"compressed evidence")
        manifest.write_text(json.dumps({"run_id": "run-0000"}))
        for folder_name in ("receipts", "eve-receipts"):
            folder = self.root / "mail-review" / folder_name
            folder.mkdir(parents=True)
            path = folder / (first.name + ".json")
            path.write_text(json.dumps({"run": first.name}))
        with patch.object(mod, "_require_activation"):
            out = mod.cleanup(self.root, apply=True)
        self.assertGreater(out["reclaimed_bytes"], 0)
        self.assertFalse(archive.exists())
        self.assertFalse(manifest.exists())
        self.assertFalse(first.exists())
        self.assertFalse((self.root / "mail-review" / "receipts" /
                          (first.name + ".json")).exists())
        self.assertEqual(self.sql_counts(), (72, 72))

    def test_unmatched_cold_manifest_fails_closed_and_journals(self):
        self.add_many()
        cold = self.root / "cold-proof-archives"
        cold.mkdir()
        (cold / "run-0000.manifest.json").write_text(
            json.dumps({"run_id": "someone-else"}))
        with patch.object(mod, "_require_activation"):
            with self.assertRaisesRegex(RuntimeError, "COLD_MANIFEST_MISMATCH"):
                mod.cleanup(self.root, apply=True)
        with closing(sqlite3.connect(self.db_path)) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM rolling72_pending").fetchone()[0], 1)

    def test_maintenance_tasks_must_be_disabled_to_activate(self):
        with patch.object(mod.os, "name", "nt"):
            with patch.object(mod.subprocess, "run") as run:
                run.return_value.returncode = 12
                with self.assertRaisesRegex(RuntimeError, "MUST_BE_DISABLED"):
                    mod._require_maintenance_window()

    def test_fast_activation_requires_verified_receipt_and_matching_sha(self):
        import hashlib
        source = self.add(0)
        external = Path(self.tmp.name) / "external"
        external.mkdir()
        copy = external / "verified.sqlite3"
        with closing(sqlite3.connect(self.db_path)) as live, \
             closing(sqlite3.connect(copy)) as dst:
            live.backup(dst)
        # Test-only logical drive simulation. Production enforces real
        # separate Windows volumes and the disabled scheduler tasks.
        def drives(path):
            return ("D:", path) if "external" in str(path) else ("C:", path)
        with patch.object(mod, "_require_maintenance_window"), \
             patch.object(mod.os.path, "splitdrive", side_effect=drives):
            with self.assertRaisesRegex(RuntimeError, "FAST_BACKUP_RECEIPT_INVALID"):
                mod.activate(self.root, backup=copy, accept_quick_verified=True)
            sha = hashlib.sha256(copy.read_bytes()).hexdigest()
            receipt = copy.with_name(copy.name + ".verified.json")
            receipt.write_text(json.dumps({
                "schema": 1, "verification": "quick",
                "backup_sha256": "0" * 64,
                "backup_bytes": copy.stat().st_size,
                "latest_run_id": "run-0000",
                "scan_runs": 1, "proof_rows": 1,
            }), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "FAST_BACKUP_HASH_MISMATCH"):
                mod.activate(self.root, backup=copy, accept_quick_verified=True)
            data = json.loads(receipt.read_text("utf-8"))
            data["backup_sha256"] = sha
            receipt.write_text(json.dumps(data), encoding="utf-8")
            result = mod.activate(self.root, backup=copy,
                                  accept_quick_verified=True)
        self.assertEqual(result["status"], "ROLLING72_ACTIVATED")
        self.assertEqual(result["backup_verification"], "quick")
        self.assertTrue((self.root / mod.POLICY).is_file())
        self.assertTrue(source.exists())

    def test_invalid_max_runs_fails(self):
        with self.assertRaisesRegex(ValueError, "MAX_RUNS"):
            mod.cleanup(self.root, apply=True, max_runs=100)


if __name__ == "__main__":
    unittest.main()
