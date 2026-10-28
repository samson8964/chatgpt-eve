"""Regression tests for the non-destructive rolling 72-run inventory."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from v4.rolling_retention import inspect


class RollingRetentionInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "sqlite").mkdir()
        (self.root / "runs").mkdir()
        self.database = self.root / "sqlite" / "v4-shadow.sqlite3"
        with sqlite3.connect(self.database) as db:
            db.execute("CREATE TABLE scan_runs (run_id TEXT PRIMARY KEY,"
                       "status TEXT, audited_at TEXT)")
            db.execute("CREATE TABLE proof_versions "
                       "(run_id TEXT, instance TEXT)")
            db.commit()

    def add_scan(self, i, *, success=True, proof=False, receipts=True,
                 complete=True):
        name = "20261028T%06dZ-%08d" % (i, i)
        run_id = "run-%04d" % i
        folder = self.root / "runs" / name
        folder.mkdir()
        (folder / "source").mkdir()
        (folder / "source" / "market_orders.csv.bz2").write_bytes(b"market")
        (folder / "deep_shadow.json").write_text(
            json.dumps({"run_id": run_id}), encoding="utf-8")
        (folder / "manifest.json").write_text(json.dumps({
            "status": "SHADOW_RECORDED" if complete else "FAILED",
            "source_input_integrity": "ALL_PARSED",
            "coverage_gate": "INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
            "failed_structure_lanes": {},
        }), encoding="utf-8")
        with sqlite3.connect(self.database) as db:
            db.execute("INSERT INTO scan_runs VALUES (?,?,?)",
                       (run_id,
                        "SHADOW_VERIFIED_OFFLINE" if success else "FAILED",
                        "%06d" % i))
            if proof:
                db.execute("INSERT INTO proof_versions VALUES (?,?)",
                           (run_id, "instance"))
            db.commit()
        if receipts:
            for rootname, filename in (
                ("receipts", name + ".json"),
                ("eve-receipts", name + ".json"),
                ("eve-receipts", name + "-2124729692.json"),
            ):
                receipt_root = self.root / "mail-review" / rootname
                receipt_root.mkdir(parents=True, exist_ok=True)
                (receipt_root / filename).write_text(
                    json.dumps({"run": name, "sent": True}), encoding="utf-8")
        return folder

    def test_72_successful_runs_keeps_all(self):
        for i in range(72):
            self.add_scan(i)
        out = inspect(self.root)
        self.assertEqual(out["retained_successful_runs"], 72)
        self.assertEqual(out["historical_success_runs"], 0)
        self.assertFalse(out["data_deleted"])

    def test_73rd_success_expires_first(self):
        for i in range(73):
            self.add_scan(i)
        out = inspect(self.root)
        self.assertEqual(out["historical_success_runs"], 1)
        self.assertEqual(out["ready_for_further_verification"], 1)
        self.assertEqual(out["old_run_samples"][0]["run_id"], "run-0000")

    def test_74th_success_expires_two(self):
        for i in range(74):
            self.add_scan(i)
        out = inspect(self.root)
        self.assertEqual(out["historical_success_runs"], 2)
        self.assertEqual(out["ready_for_further_verification"], 2)

    def test_failed_scan_does_not_advance_window(self):
        for i in range(72):
            self.add_scan(i)
        self.add_scan(72, success=False)
        self.add_scan(73, complete=False)
        out = inspect(self.root)
        self.assertEqual(out["current_successful_runs"], 72)
        self.assertEqual(out["historical_success_runs"], 0)

    def test_unpruned_sqlite_proof_blocks_expired(self):
        self.add_scan(0, proof=True)
        for i in range(1, 73):
            self.add_scan(i)
        out = inspect(self.root)
        self.assertEqual(out["blocked_old_runs"], 1)
        self.assertIn("HOT_SQL_PROOFS_NOT_YET_PRUNED",
                      out["old_run_samples"][0]["blockers"])

    def test_missing_delivery_receipt_blocks_expired(self):
        self.add_scan(0, receipts=False)
        for i in range(1, 73):
            self.add_scan(i)
        out = inspect(self.root)
        self.assertEqual(out["blocked_old_runs"], 1)
        self.assertIn("LADYBABA_RECEIPT_UNVERIFIED",
                      out["old_run_samples"][0]["blockers"])

    def test_unmapped_old_sqlite_is_not_guessed_into_purge(self):
        with sqlite3.connect(self.database) as db:
            db.execute("INSERT INTO scan_runs VALUES (?,?,?)",
                       ("old-missing", "SHADOW_VERIFIED_OFFLINE", "000"))
            db.commit()
        self.add_scan(1)
        out = inspect(self.root)
        self.assertEqual(out["unmapped_sqlite_rows"], 1)
        self.assertIn("UNMAPPED_SQLITE_ROWS_REQUIRE_SEPARATE_MIGRATION",
                      out["warnings"])

    def test_inventory_rejects_other_keep_size(self):
        with self.assertRaisesRegex(ValueError, "EXACTLY_72"):
            inspect(self.root, keep_runs=24)

    def test_run_directory_symlink_not_followed(self):
        with tempfile.TemporaryDirectory() as external:
            path = self.add_scan(0)
            try:
                (path / "source" / "outside").symlink_to(
                    Path(external), target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("No symlink privilege on this Windows host")
            for i in range(1, 73):
                self.add_scan(i)
            out = inspect(self.root)
            self.assertEqual(out["blocked_old_runs"], 1)
            self.assertIn("RUN_DIRECTORY_UNSAFE",
                          out["old_run_samples"][0]["blockers"])

    def test_inspection_never_changes_database_or_files(self):
        self.add_scan(0)
        before = self.database.stat().st_mtime_ns
        files = sorted(str(p) for p in self.root.rglob("*"))
        self.assertEqual(inspect(self.root)["status"],
                         "READ_ONLY_72_RUN_RETENTION_INSPECTION")
        self.assertEqual(self.database.stat().st_mtime_ns, before)
        self.assertEqual(sorted(str(p) for p in self.root.rglob("*")), files)


if __name__ == "__main__":
    unittest.main()
