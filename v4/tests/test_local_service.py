import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from v4.local_service import storage_check, backup_due, execute, main
from v4.structure_registry import STRUCTURES


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

    def test_no_old_opportunity_replayed_when_low_disk(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("sys.argv", ["local_service", "--data-root", td]), \
                 patch("v4.local_service.execute",
                       return_value={"status": "SKIPPED_LOW_DISK",
                                     "disk": {"free_gib": 9}}), \
                 patch("v4.local_service._log_storage_health",
                       return_value={"severity": "STOP"}), \
                 patch("v4.research_mail.send_review") as gmail, \
                 patch("v4.game_mail_review.send_review_to_game") as game:
                exit_code = main()
            self.assertEqual(exit_code, 4)
            gmail.assert_not_called()
            game.assert_not_called()
            log = (Path(td) / "logs" / "shadow-task.log").read_text("utf-8")
            self.assertIn("LOW_DISK_NO_CURRENT_RUN", log)

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
                        "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
                        "structure_health":{name:{"status":"COMPLETE","pages":1,"pages_fetched":1}
                                            for name in STRUCTURES}}
            def save(r):
                calls.append("backup")
                return {"sqlite_integrity":"ok","proof_versions":31931}
            with patch("v4.local_service.storage_check",
                       return_value={"free_gib":300,"enough_space":True}):
                result=execute(root,scanner=scan,backup_fn=save)
            self.assertEqual(calls,["scan","backup"])
            self.assertEqual(result["status"],"SHADOW_RECORDED")
            self.assertEqual(result["backup_proofs"],31931)
            self.assertFalse(result["mail_enabled"])


    def test_partial_scan_is_not_reported_successful(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            recorded=[]
            def scan(r):
                return {"status":"SHADOW_RECORDED","mail_enabled":False,
                        "run_folder":str(r/"runs"/"now"),"sqlite_unique_proofs":100,
                        "coverage_gate":"PARTIAL_UNVERIFIED",
                        "structure_health":{"four_h":{"status":"FAILED"},
                                            "cj":{"status":"COMPLETE","pages":54,"pages_fetched":54},
                                            "o4t":{"status":"COMPLETE","pages":8,"pages_fetched":8}}}
            def save(r):
                recorded.append("backup")
                return {"sqlite_integrity":"ok","proof_versions":100}
            with patch("v4.local_service.storage_check",
                       return_value={"free_gib":300,"enough_space":True}):
                result=execute(root,scanner=scan,backup_fn=save)
            self.assertEqual(result["status"],"DEGRADED_PARTIAL_COVERAGE")
            self.assertEqual(result["structure_status"]["four_h"],"FAILED")
            self.assertEqual(recorded,["backup"])
            self.assertFalse(result["mail_enabled"])

    def test_missing_structure_health_is_degraded(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with patch("v4.local_service.storage_check",
                       return_value={"free_gib":300,"enough_space":True}):
                result=execute(root,scanner=lambda r:{
                    "status":"SHADOW_RECORDED","mail_enabled":False,
                    "run_folder":str(r/"runs"/"now"),
                    "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
                    "structure_health":{}},
                    backup_fn=lambda r:{"sqlite_integrity":"ok","proof_versions":0})
            self.assertEqual(result["status"],"DEGRADED_PARTIAL_COVERAGE")


    def test_all_structures_complete_but_single_public_order_quarantined(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            def scan(r):
                return {"status":"SHADOW_RECORDED","mail_enabled":False,
                        "run_folder":str(r/"runs"/"now"),
                        "coverage_gate":"PARTIAL_UNVERIFIED",
                        "source_input_integrity":"PARTIAL_QUARANTINED",
                        "invalid_public_orders":1,"invalid_structure_orders":0,
                        "rejected_input_orders":1,
                        "structure_health":{
                            name:{"status":"COMPLETE","pages":2,"pages_fetched":2}
                            for name in STRUCTURES}}
            with patch("v4.local_service.storage_check",
                       return_value={"free_gib":300,"enough_space":True}):
                result=execute(root,scanner=scan,
                               backup_fn=lambda r:{"sqlite_integrity":"ok",
                                                   "proof_versions":1})
            self.assertEqual(result["status"],"DEGRADED_INPUT_QUARANTINE")
            self.assertEqual(result["invalid_public_orders"],1)
            self.assertEqual(result["invalid_structure_orders"],0)
            self.assertEqual(result["rejected_input_orders"],1)
            self.assertTrue(all(v=="COMPLETE"
                                for v in result["structure_status"].values()))
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
