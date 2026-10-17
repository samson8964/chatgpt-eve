"""Offline regression for explicit one-click V4 scan trigger.

The desktop button only submits the ALREADY installed EVE-V4-Shadow Windows
task, never invokes local_service or adds its own crawler process. No real
scheduler access or desktop/display required in CI.
"""
from __future__ import annotations

import json
import subprocess
import unittest
from concurrent.futures import Future
from unittest.mock import Mock

from v4.manual_scan import request_full_scan, _START_SCRIPT
from v4.desktop_widget import DesktopWidget


class ManualTaskRequestTests(unittest.TestCase):
    def test_requests_exact_existing_scheduler_task_with_overlap_check(self):
        runner=Mock(return_value=subprocess.CompletedProcess(
            args=["powershell.exe"],returncode=0,
            stdout='{"status":"START_REQUESTED"}',stderr=""))
        result=request_full_scan(runner=runner,platform="win32")
        self.assertEqual(result,{"status":"START_REQUESTED"})
        command=runner.call_args.args[0]
        self.assertEqual(command[:3],["powershell.exe","-NoProfile","-NonInteractive"])
        script=command[-1]
        self.assertIn("Get-ScheduledTask -TaskName 'EVE-V4-Shadow'",script)
        self.assertIn("Start-ScheduledTask -InputObject $t",script)
        self.assertIn("$t.Settings.MultipleInstances.ToString() -ne 'IgnoreNew'",script)
        self.assertIn("$state -ne 'Ready'",script)
        self.assertNotIn("python.exe",script)
        self.assertNotIn("v4.local_service",script)
        self.assertNotIn("Send-MailMessage",script)
        self.assertEqual(runner.call_args.kwargs["timeout"],15)
        self.assertFalse(runner.call_args.kwargs["check"])

    def test_no_request_on_unsupported_system(self):
        runner=Mock()
        result=request_full_scan(runner=runner,platform="linux")
        self.assertEqual(result["status"],"WINDOWS_REQUIRED")
        runner.assert_not_called()

    def test_supported_no_launch_states(self):
        for status in ("ALREADY_RUNNING","NOT_READY","UNSAFE_MULTIPLE_INSTANCES"):
            with self.subTest(status=status):
                runner=Mock(return_value=subprocess.CompletedProcess(
                    args=[],returncode=0,
                    stdout=json.dumps({"status":status}),stderr=""))
                self.assertEqual(
                    request_full_scan(runner=runner,platform="win32")["status"],
                    status)

    def test_failure_never_counts_as_task_started(self):
        cases=[
            subprocess.CompletedProcess(args=[],returncode=1,stdout="",stderr="Access denied"),
            subprocess.CompletedProcess(args=[],returncode=0,stdout="not json",stderr=""),
            subprocess.CompletedProcess(args=[],returncode=0,stdout='{"status":"LAUNCHED"}',stderr=""),
        ]
        for response in cases:
            with self.subTest(response=response):
                runner=Mock(return_value=response)
                self.assertEqual(
                    request_full_scan(runner=runner,platform="win32")["status"],
                    "TASK_START_FAILED")
        def timeout(*args,**kwargs):
            raise subprocess.TimeoutExpired(cmd="powershell.exe",timeout=15)
        self.assertEqual(request_full_scan(runner=timeout,platform="win32")
                         ["status"],"TASK_START_FAILED")


class ManualDesktopActionTests(unittest.TestCase):
    def new_widget(self,state="Ready"):
        # Construct only widget state needed by callback; Tk isn't started.
        widget=DesktopWidget.__new__(DesktopWidget)
        widget.closed=False
        widget.task={"state":state,"last_run":"2026-10-18T03:23:00"}
        widget.manual_future=None
        widget.manual_started_request_at=None
        widget.manual_prior_last_run=None
        widget.manual_message=""
        widget.manual_message_color="muted"
        widget.manual_button=Mock()
        widget.manual_label=Mock()
        widget.manual_pool=Mock()
        widget.last_query_at=100.0
        return widget

    def test_click_submits_worker_once_without_blocking_ui(self):
        widget=self.new_widget()
        future=Future()
        widget.manual_pool.submit.return_value=future
        widget.start_full_scan()
        self.assertIs(widget.manual_future,future)
        self.assertEqual(widget.manual_prior_last_run,
                         "2026-10-18T03:23:00")
        widget.manual_pool.submit.assert_called_once()
        self.assertEqual(widget.manual_pool.submit.call_args.args[0],
                         request_full_scan)
        widget.start_full_scan()
        widget.manual_pool.submit.assert_called_once()
        self.assertEqual(widget.manual_message_color,"blue")

    def test_disabled_or_running_task_is_not_started(self):
        for state in ("Running","Disabled","Missing","Unknown"):
            widget=self.new_widget(state)
            widget.start_full_scan()
            widget.manual_pool.submit.assert_not_called()

    def test_future_accepted_stays_disabled_until_scheduler_reports_started(self):
        widget=self.new_widget()
        future=Future()
        future.set_result({"status":"START_REQUESTED"})
        widget.manual_future=future
        widget._refresh_manual_action(100.0)
        self.assertIsNone(widget.manual_future)
        self.assertEqual(widget.manual_started_request_at,100.0)
        self.assertEqual(widget.last_query_at,0.0)
        self.assertIn("已提交",widget.manual_message)
        widget.manual_button.configure.assert_called_with(state="disabled")
        widget._refresh_manual_action(102.0)
        widget.manual_button.configure.assert_called_with(state="disabled")
        widget.task["state"]="Running"
        widget._refresh_manual_action(105.0)
        self.assertIsNone(widget.manual_started_request_at)
        self.assertIn("正在运行",widget.manual_message)
        widget.manual_button.configure.assert_called_with(state="disabled")
        widget.task["state"]="Ready"
        widget._refresh_manual_action(106.0)
        widget.manual_button.configure.assert_called_with(state="normal")

    def test_fast_task_last_run_change_confirms_trigger_without_claiming_success(self):
        widget=self.new_widget()
        future=Future()
        future.set_result({"status":"START_REQUESTED"})
        widget.manual_future=future
        widget.manual_prior_last_run=widget.task["last_run"]
        widget._refresh_manual_action(1.0)
        widget.task["last_run"]="2026-10-18T04:45:00"
        widget._refresh_manual_action(2.0)
        self.assertIn("已触发",widget.manual_message)
        self.assertNotIn("成功",widget.manual_message)
        widget.manual_button.configure.assert_called_with(state="normal")

    def test_task_never_confirmed_does_not_claim_succeeded(self):
        widget=self.new_widget()
        future=Future()
        future.set_result({"status":"START_REQUESTED"})
        widget.manual_future=future
        widget._refresh_manual_action(5.0)
        widget._refresh_manual_action(36.0)
        self.assertIn("未能确认",widget.manual_message)
        self.assertIsNone(widget.manual_started_request_at)

    def test_rejection_and_worker_failure_keep_ui_usable(self):
        for status in ("ALREADY_RUNNING","NOT_READY","UNSAFE_MULTIPLE_INSTANCES",
                       "TASK_START_FAILED"):
            widget=self.new_widget()
            future=Future()
            future.set_result({"status":status})
            widget.manual_future=future
            widget._refresh_manual_action(1.0)
            self.assertIsNone(widget.manual_future)
            self.assertIsNone(widget.manual_started_request_at)
            self.assertNotIn("已提交",widget.manual_message)
            self.assertEqual(widget.manual_button.configure.call_args.kwargs["state"],
                             "normal")


if __name__=="__main__":
    unittest.main()
