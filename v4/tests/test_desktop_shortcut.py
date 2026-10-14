"""Validate desktop shortcut installer without creating links in CI."""
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "install_desktop_widget.ps1"


class DesktopShortcutTests(unittest.TestCase):
    def test_installer_creates_user_desktop_link_to_pythonw_only(self):
        code=SCRIPT.read_text("utf-8")
        for expected in (
            "GetFolderPath('Desktop')",
            "CreateShortcut",
            "pythonw.exe",
            "-m v4.desktop_widget",
            "WorkingDirectory",
            "Start-Process -FilePath $shortcutPath",
            "[switch]$AutoStart",
            "GetFolderPath('Startup')",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected,code)
        self.assertNotIn("Register-ScheduledTask",code)
        self.assertNotIn("EVE_MARKET_API_KEY",code)

    @unittest.skipUnless(sys.platform == "win32", "PowerShell parser available on Windows CI")
    def test_installer_parses_as_windows_powershell(self):
        escaped=str(SCRIPT).replace("'","''")
        parse=(
            "$tokens=$null; $errors=$null; "
            "[void][System.Management.Automation.Language.Parser]::ParseFile("
            f"'{escaped}', [ref]$tokens, [ref]$errors); "
            "if ($errors.Count) { $errors | Out-String | Write-Error; exit 1 }"
        )
        done=subprocess.run(["powershell.exe","-NoProfile","-NonInteractive",
                             "-Command",parse],text=True,capture_output=True,
                            timeout=20,check=False)
        self.assertEqual(done.returncode,0,done.stderr[-1200:])


if __name__=="__main__":
    unittest.main()
