"""Safety and Windows syntax checks for V4 shadow scheduled task installation."""
from __future__ import annotations
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "install_windows_task.ps1"


class InstallWindowsTaskTests(unittest.TestCase):
    def test_registration_remains_opt_in_and_shadow_only(self):
        code = SCRIPT.read_text("utf-8")
        self.assertIn("[switch]$Install", code)
        self.assertIn("if (-not $Install)", code)
        self.assertIn("pythonw.exe", code)
        self.assertIn("New-ScheduledTaskPrincipal", code)
        self.assertIn("Interactive", code)
        self.assertIn("-MultipleInstances IgnoreNew", code)
        self.assertIn("SHADOW ONLY", code)
        self.assertIn("Register-ScheduledTask", code)

    def test_installation_requires_fully_verified_prior_run(self):
        code = SCRIPT.read_text("utf-8")
        for gate in (
            "LATEST_SHADOW_RUN_NOT_FULLY_VERIFIED_FOR_UNATTENDED_MODE",
            "INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
            "source_input_integrity", "ALL_PARSED",
            "sqlite_integrity", "sqlite_count_matches_report",
            "STRUCTURE_LANE_NOT_COMPLETE",
            "pages_fetched", "mail_enabled",
        ):
            with self.subTest(gate=gate):
                self.assertIn(gate, code)

    @unittest.skipUnless(sys.platform == "win32", "Windows PowerShell syntax check")
    def test_installer_powershell_parser(self):
        # Parse, do NOT execute any scheduled-task or filesystem operations.
        escaped = str(SCRIPT).replace("'", "''")
        command = (
            "$tokens=$null; $errors=$null; "
            "[void][System.Management.Automation.Language.Parser]::ParseFile("
            f"'{escaped}', [ref]$tokens, [ref]$errors); "
            "if ($errors.Count -gt 0) { $errors | Out-String | Write-Error; exit 1 }"
        )
        completed = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive",
                                    "-Command", command], capture_output=True, text=True,
                                   check=False, timeout=20)
        self.assertEqual(completed.returncode, 0,
                         (completed.stdout + completed.stderr)[-2000:])


if __name__ == "__main__":
    unittest.main()
