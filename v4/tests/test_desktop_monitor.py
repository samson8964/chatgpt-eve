"""V4 desktop widget safe local read-only behaviour: no GUI display required."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v4.desktop_status import elapsed_clock, human_clock, read_snapshot, _log_events
from v4.desktop_widget import _status_style, query_windows_task


class V4DesktopMonitorTests(unittest.TestCase):
    def make_root(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root/"runs"/"20261014T060000Z-abc").mkdir(parents=True)
        (root/"logs").mkdir()
        prior = root/"runs"/"20261014T060000Z-abc"
        (prior/"manifest.json").write_text(json.dumps({
            "status":"SHADOW_RECORDED",
            "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
            "sqlite_unique_proofs":32900,
            "invalid_public_orders":0,
            "zero_remaining_public_orders":4,
            "structure_health":{
                name:{"status":"COMPLETE","pages":1,"pages_fetched":1}
                for name in ("four_h","cj","o4t")}}),encoding="utf-8")
        (prior/"deep_shadow.json").write_text(json.dumps({
            "model_candidates":15
        }),encoding="utf-8")
        return root

    def test_completed_success_is_read_from_local_files_and_log(self):
        root=self.make_root()
        (root/"logs"/"shadow-task.log").write_text(
            'START 2026-10-14T06:00:00+00:00\n'
            'full_scan: starting\n'
            'full_scan: completed\n'
            'deep_scan: starting\n'
            'deep_scan: completed\n'
            'RESULT {"status":"SHADOW_RECORDED","mail_enabled":false}\n',
            encoding="utf-8")
        task={"state":"Ready","last_result":0,
              "next_run":"2026-10-14T16:23:00"}
        got=read_snapshot(root,task)
        self.assertEqual(got["status"],"SHADOW_RECORDED")
        self.assertEqual(got["proofs"],32900)
        self.assertEqual(got["model_candidates"],15)
        self.assertEqual(got["zero_remaining_public_orders"],4)
        self.assertEqual(got["structures"],
                         {"four_h":"COMPLETE","cj":"COMPLETE","o4t":"COMPLETE"})
        self.assertTrue(got["read_only"])
        self.assertFalse(got["mail_enabled"])
        self.assertEqual(human_clock("2026-10-14T16:23:00")[-5:],"16:23")

    def test_running_shows_actual_log_phase_not_fabricated_percent(self):
        root=self.make_root()
        running=root/"runs"/"20261014T070000Z-current"
        running.mkdir()
        (running/"manifest.json").write_text(json.dumps({
            "status":"STARTED","started_at":"2026-10-14T07:00:00+00:00"}),
            encoding="utf-8")
        (root/"logs"/"shadow-task.log").write_text(
            'START 2026-10-14T06:00:00+00:00\n'
            'RESULT {"status":"SHADOW_RECORDED"}\n'
            'START 2026-10-14T07:00:00+00:00\n'
            'full_scan: starting\n'
            'full_scan: completed\n'
            'deep_scan: starting\n',encoding="utf-8")
        got=read_snapshot(root,{"state":"Running","last_result":0})
        self.assertEqual(got["status"],"RUNNING")
        self.assertEqual(got["phase"],"建筑与合同分析")
        self.assertEqual(got["last_completed_folder"],"20261014T060000Z-abc")
        self.assertEqual(got["latest_result_status"],"SHADOW_RECORDED")
        self.assertEqual(got["elapsed_start"],"2026-10-14T07:00:00+00:00")
        self.assertNotIn("percent",got)

    def test_partial_quarantine_not_masked_as_success(self):
        root=self.make_root()
        (root/"logs"/"shadow-task.log").write_text(
            'START 2026-10-14T07:00:00+00:00\n'
            'RESULT {"status":"DEGRADED_INPUT_QUARANTINE",'
            '"invalid_public_orders":4,"mail_enabled":false}\n',encoding="utf-8")
        got=read_snapshot(root,{"state":"Ready","last_result":2})
        self.assertEqual(got["status"],"DEGRADED_INPUT_QUARANTINE")
        self.assertEqual(_status_style(got["status"])[1],"amber")

    def test_scheduler_error_and_absent_data_do_not_assert_success(self):
        with tempfile.TemporaryDirectory() as td:
            got=read_snapshot(Path(td),{"state":"MISSING"})
            self.assertEqual(got["status"],"TASK_MISSING")
            self.assertIsNone(got["proofs"])
            self.assertEqual(got["structures"]["cj"],"UNKNOWN")
        self.assertEqual(elapsed_clock("invalid"),"--:--")

    def test_failed_last_attempt_is_not_covered_by_old_success(self):
        root=self.make_root()
        (root/"logs"/"shadow-task.log").write_text(
            'START 2026-10-14T06:00:00+00:00\n'
            'RESULT {"status":"SHADOW_RECORDED"}\n'
            'START 2026-10-14T07:00:00+00:00\n'
            'FAILED ConnectionError no access\n',encoding="utf-8")
        got=read_snapshot(root,{"state":"Ready","last_result":1})
        self.assertEqual(got["status"],"FAILED")
        self.assertTrue(got["last_log_error"].startswith("ConnectionError"))

    def test_windows_task_query_has_hidden_console_and_no_api_access(self):
        captured=[]
        def fake_runner(cmd,**kwargs):
            captured.append((cmd,kwargs))
            return subprocess.CompletedProcess(
                cmd,0,'{"state":"Running","next_run":"2026-10-14T16:23:00",'
                '"last_result":0}',"")
        with patch("v4.desktop_widget.sys.platform","win32"):
            info=query_windows_task(runner=fake_runner)
        self.assertEqual(info["state"],"Running")
        self.assertEqual(info["last_result"],0)
        cmd,kwargs=captured[0]
        self.assertEqual(cmd[0],"powershell.exe")
        self.assertEqual(kwargs["stdin"],subprocess.DEVNULL)
        self.assertEqual(kwargs["timeout"],12)
        self.assertNotIn("Authorization",str(cmd))
        self.assertNotIn("MAIL_API_KEY",str(cmd))


if __name__ == "__main__":
    unittest.main()
