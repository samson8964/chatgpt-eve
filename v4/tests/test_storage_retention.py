"""Fail-closed local backup rotation regressions, with small SQLite fixtures."""
from __future__ import annotations

import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v4.storage_retention import rotate_backups


def valid_backup(folder: Path, stamp: str, *, valid: bool = True) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    name = folder / ("v4-shadow-" + stamp + ".sqlite3")
    if not valid:
        name.write_text("not a SQLite database", encoding="ascii")
        return name
    with closing(sqlite3.connect(name)) as db:
        db.execute("CREATE TABLE scan_runs (run_id TEXT)")
        db.execute("CREATE TABLE proof_versions (run_id TEXT)")
        db.execute("INSERT INTO scan_runs VALUES (?)", (stamp,))
        db.commit()
    return name


class LocalBackupRetentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / "backups"

    def create(self, count=5):
        return [valid_backup(self.folder, f"202610{d:02d}T130000Z")
                for d in range(17, 17+count)]

    def test_dry_run_never_deletes(self):
        paths = self.create(5)
        result = rotate_backups(self.root)
        self.assertEqual(result["status"], "DRY_RUN")
        self.assertEqual(result["old_backups"], 2)
        self.assertEqual(result["deleted"], 0)
        self.assertTrue(all(path.exists() for path in paths))

    def test_apply_keeps_latest_three_valid_days(self):
        paths = self.create(5)
        report = rotate_backups(
            self.root, apply=True, expected_newest=paths[-1])
        self.assertEqual(report["status"], "ROTATED")
        self.assertEqual(report["deleted"], 2)
        self.assertEqual(report["old_backups"], 2)
        self.assertTrue(all(p.exists() for p in paths[-3:]))
        self.assertTrue(all(not p.exists() for p in paths[:2]))

    def test_retained_corrupt_backup_prevents_all_deletion(self):
        paths = self.create(5)
        paths[-1].write_bytes(b"corrupted backup")
        with self.assertRaises(sqlite3.DatabaseError):
            rotate_backups(self.root, apply=True)
        self.assertEqual(len(list(self.folder.iterdir())), 5)

    def test_missing_schema_prevents_all_deletion(self):
        paths = self.create(5)
        with closing(sqlite3.connect(paths[-1])) as db:
            db.execute("DROP TABLE proof_versions")
            db.commit()
        with self.assertRaisesRegex(RuntimeError, "SCHEMA_INVALID"):
            rotate_backups(self.root, apply=True)
        self.assertTrue(all(p.exists() for p in paths))

    def test_no_prune_when_three_latest_created_same_day(self):
        self.create(5)
        for hour in ("140000", "150000"):
            valid_backup(self.folder, "20261021T" + hour + "Z")
        report = rotate_backups(self.root, apply=True)
        self.assertEqual(report["status"], "BLOCKED_RECENT_DAYS_NOT_DISTINCT")
        self.assertEqual(report["deleted"], 0)

    def test_guard_against_unexpected_newest_backup(self):
        paths = self.create(5)
        with self.assertRaisesRegex(RuntimeError, "NEW_BACKUP_NOT_LATEST"):
            rotate_backups(self.root, apply=True, expected_newest=paths[0])
        self.assertTrue(all(p.exists() for p in paths))

    def test_unrelated_files_and_directories_untouched(self):
        self.create(5)
        dirs = ["runs", "sqlite", "opportunity-push", "mail-review", "config"]
        for name in dirs:
            f=self.root/name/"sentinel.txt"
            f.parent.mkdir(parents=True)
            f.write_text("preserve")
        keep=self.folder/"user-created-offline-backup.sqlite3"
        keep.write_bytes(b"untouched")
        rotate_backups(self.root, apply=True)
        self.assertTrue(keep.exists())
        self.assertTrue(all(
            (self.root/name/"sentinel.txt").read_text()=="preserve"
            for name in dirs
        ))

    def test_no_apply_when_three_or_fewer_backups(self):
        paths = self.create(3)
        report=rotate_backups(self.root,apply=True)
        self.assertEqual(report["status"],"NOT_NEEDED")
        self.assertEqual(report["deleted"],0)
        self.assertTrue(all(p.exists() for p in paths))

    def test_service_rotates_after_valid_backup_without_changing_scan(self):
        from v4.local_service import execute
        from v4.structure_registry import STRUCTURES

        def scan(root):
            return {
                "status": "SHADOW_RECORDED", "mail_enabled": False,
                "run_folder": str(root/"runs"/"test-success"),
                "coverage_gate":
                    "INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
                "structure_health": {
                    lane: {"status": "COMPLETE", "pages": 1,
                           "pages_fetched": 1}
                    for lane in STRUCTURES
                },
            }

        new = self.root/"backups"/"v4-shadow-20261024T000000Z.sqlite3"
        with patch("v4.local_service.storage_check",
                   return_value={"free_gib": 227, "enough_space": True}), \
             patch("v4.storage_retention.rotate_backups",
                   return_value={"status": "ROTATED", "deleted": 9}) as rotate:
            result=execute(self.root,scanner=scan,
                backup_fn=lambda _: {
                    "sqlite_integrity": "ok", "proof_versions": 1234,
                    "path": str(new),
                })
        self.assertEqual(result["status"], "SHADOW_RECORDED")
        self.assertEqual(result["backup_retention"]["deleted"], 9)
        rotate.assert_called_once_with(
            self.root, apply=True, expected_newest=new)

    def test_retention_failure_cannot_interrupt_shadow_result_or_mail(self):
        from v4.local_service import execute
        from v4.structure_registry import STRUCTURES

        def scan(root):
            return {
                "status": "SHADOW_RECORDED", "mail_enabled": False,
                "run_folder": str(root/"runs"/"test-success"),
                "coverage_gate":
                    "INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
                "structure_health": {
                    lane: {"status": "COMPLETE", "pages": 1,
                           "pages_fetched": 1}
                    for lane in STRUCTURES
                },
            }
        with patch("v4.local_service.storage_check",
                   return_value={"free_gib": 227, "enough_space": True}), \
             patch("v4.storage_retention.rotate_backups",
                   side_effect=RuntimeError("CHECK_FAILED")):
            result=execute(self.root,scanner=scan,
                backup_fn=lambda _: {
                    "sqlite_integrity": "ok", "proof_versions": 1234,
                    "path": str(self.root/"backups"/"new.sqlite3"),
                })
        self.assertEqual(result["status"], "SHADOW_RECORDED")
        self.assertFalse(result["mail_enabled"])
        self.assertEqual(result["backup"], "COMPLETE")
        self.assertEqual(result["backup_retention"]["status"], "BLOCKED")

    def test_symlink_backup_is_not_pruned(self):
        with tempfile.TemporaryDirectory() as outside:
            try:
                self.create(5)
                src=Path(outside)/"external.sqlite3"
                src.write_bytes(b"external")
                (self.folder/"v4-shadow-20261016T130000Z.sqlite3").symlink_to(src)
            except (NotImplementedError, OSError):
                self.skipTest("Windows symlink permissions unavailable")
            with self.assertRaisesRegex(RuntimeError,"BACKUP_FILE_UNSAFE"):
                rotate_backups(self.root,apply=True)
            self.assertTrue(src.exists())


if __name__ == "__main__":
    unittest.main()
