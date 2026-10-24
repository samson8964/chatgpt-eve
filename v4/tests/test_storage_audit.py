import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from v4.storage_audit import inspect


class StorageAuditTests(unittest.TestCase):
    def test_reports_directory_sizes_without_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"runs").mkdir()
            f=root/"runs"/"old-proof.jsonl"
            f.write_bytes(b"x"*10000)
            report=inspect(root)
            self.assertEqual(report["status"],"READ_ONLY_STORAGE_AUDIT")
            self.assertEqual(report["directories"]["runs"]["files"],1)
            self.assertEqual(report["hot_sqlite"]["status"],"NOT_FOUND")
            self.assertFalse(report["backup_files_deleted"])
            self.assertTrue(f.is_file())

    def test_reports_allocated_pages_and_row_counts_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            folder=root/"sqlite"
            folder.mkdir()
            path=folder/"v4-shadow.sqlite3"
            with closing(sqlite3.connect(path)) as con:
                con.execute(
                    "CREATE TABLE scan_runs (run_id TEXT, proof_count INTEGER, audited_at TEXT)")
                con.execute("CREATE TABLE proof_versions (id INTEGER, proof_json TEXT)")
                con.execute(
                    "INSERT INTO scan_runs VALUES ('v4-test', 1, '2026-10-24T00:00:00Z')")
                con.execute("INSERT INTO proof_versions VALUES (1, 'example')")
                con.commit()
            size_before=path.stat().st_size
            report=inspect(root,deep=True)
            self.assertEqual(report["hot_sqlite"]["status"],"READ_ONLY")
            self.assertGreater(report["hot_sqlite"]["page_size_bytes"],0)
            self.assertEqual(report["hot_sqlite"]["scan_run_count"],1)
            self.assertEqual(report["hot_sqlite"]["proof_row_count"],1)
            sample=report["hot_sqlite"]["proof_json_sample"]
            self.assertEqual(sample["status"],"ESTIMATE_NOT_EXACT")
            self.assertGreater(sample["avg_proof_json_bytes"],0)
            self.assertEqual(report["hot_sqlite"]["recent_scan_runs"],[
                {"run_id":"v4-test","proof_count":1,
                 "audited_at":"2026-10-24T00:00:00Z"}])
            self.assertEqual(path.stat().st_size,size_before)

    def test_backup_inventory_includes_unexpected_partial_files(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            folder=root/"backups"
            folder.mkdir()
            (folder/"v4-shadow-20261023T000000Z.sqlite3").write_bytes(b"x"*8)
            (folder/"v4-shadow-20261024T000000Z.sqlite3.part").write_bytes(b"x"*16)
            report=inspect(root)
            inventory=report["backup_inventory"]
            self.assertEqual(inventory["files"],2)
            self.assertIn("v4-shadow-20261024T000000Z.sqlite3.part",
                          inventory["unrecognized_files"])
            self.assertEqual(
                inventory["largest_files"][0]["bytes"],16)
            self.assertTrue((folder/"v4-shadow-20261024T000000Z.sqlite3.part").exists())

    def test_missing_root_reports_empty_directory_breakdown(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"missing"
            value=inspect(root)
            self.assertEqual(value["directories"],{})
            self.assertEqual(value["hot_sqlite"]["status"],"NOT_FOUND")


if __name__=="__main__":
    unittest.main()
