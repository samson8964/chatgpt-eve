"""Backup promotion happens only after full integrity verification."""
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from v4.local_backup import backup


class LocalBackupAtomicTests(unittest.TestCase):
    def test_verified_backup_published_once_and_no_part_remains(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            folder=root/"sqlite"
            folder.mkdir()
            source=folder/"v4-shadow.sqlite3"
            with closing(sqlite3.connect(source)) as db:
                db.execute("CREATE TABLE proof_versions (instance TEXT)")
                db.execute("CREATE TABLE scan_runs (run_id TEXT)")
                db.execute("INSERT INTO scan_runs VALUES ('test')")
                db.commit()
            result=backup(root)
            self.assertEqual(result["sqlite_integrity"],"ok")
            self.assertEqual(result["scan_runs"],1)
            dest=Path(result["path"])
            self.assertTrue(dest.is_file())
            self.assertFalse(dest.with_name(dest.name+".part").exists())
            with closing(sqlite3.connect(dest)) as db:
                self.assertEqual(db.execute(
                    "PRAGMA integrity_check").fetchone()[0],"ok")
            self.assertTrue(source.is_file())

    def test_missing_ledger_table_never_publishes_partial_copy(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            folder=root/"sqlite"
            folder.mkdir()
            source=folder/"v4-shadow.sqlite3"
            with closing(sqlite3.connect(source)) as db:
                db.execute("CREATE TABLE scan_runs (run_id TEXT)")
                db.commit()
            with self.assertRaises(sqlite3.DatabaseError):
                backup(root)
            copies=list((root/"backups").iterdir())
            self.assertEqual(copies,[])


if __name__=="__main__":
    unittest.main()
