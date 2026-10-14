import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from v4.local_service import storage_check, backup_due, execute


class LocalServiceTests(unittest.TestCase):
    def test_small_disk_skips_without_new_scan(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch("v4.local_service.storage_check",
                       return_value={"free_gib": 1, "enough_space": False}):
                called=[]
                value=execute(root,scanner=lambda _:called.append(True))
            self.assertEqual(value["status"],"SKIPPED_LOW_DISK")
            self.assertEqual(called,[])
            self.assertFalse(value["mail_enabled"])

    def test_storage_capacity_boundary(self):
        self.assertFalse(storage_check(Path("."),free_bytes=19*1024**3)["enough_space"])
        self.assertTrue(storage_check(Path("."),free_bytes=20*1024**3)["enough_space"])

    def test_success_scans_once_and_backs_up(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            calls=[]
            def scan(r):
                calls.append("scan")
                return {"status":"SHADOW_RECORDED","mail_enabled":False,
                        "run_folder":str(r/"runs"/"now"),"sqlite_unique_proofs":31931,
                        "coverage_gate":"PARTIAL_UNVERIFIED"}
            def save(r):
                calls.append("backup")
                return {"sqlite_integrity":"ok","proof_versions":31931}
            with patch("v4.local_service.storage_check",
                       return_value={"free_gib":300,"enough_space":True}):
                result=execute(root,scanner=scan,backup_fn=save)
            self.assertEqual(calls,["scan","backup"])
            self.assertEqual(result["backup_proofs"],31931)
            self.assertFalse(result["mail_enabled"])

    def test_never_accepts_scan_claiming_mail(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("v4.local_service.storage_check",
                       return_value={"free_gib":300,"enough_space":True}):
                with self.assertRaisesRegex(RuntimeError,"MAIL_NOT_DISABLED"):
                    execute(Path(td),scanner=lambda _:{"status":"SHADOW_RECORDED",
                                                        "mail_enabled":True})

    def test_daily_backup_is_not_repeated(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=root/"backups"
            p.mkdir()
            (p/"v4-shadow-20261014T000000Z.sqlite3").write_bytes(b"fixture")
            self.assertFalse(backup_due(root,datetime.now(timezone.utc)))


if __name__=="__main__":
    unittest.main()
