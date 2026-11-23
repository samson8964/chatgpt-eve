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
        # PowerShell reserves $args as an automatic array local to functions.
        # WScript shortcut Arguments is a COM string property.
        self.assertNotIn("$link.Arguments = $args",code)
        self.assertIn("$link.Arguments = [string]$ArgumentLine",code)
        self.assertIn("-ArgumentLine $shortcutArguments",code)

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


    @unittest.skipUnless(sys.platform == "win32", "Windows PowerShell and COM mock")
    def test_create_shortcut_receives_real_string_not_powershell_auto_args(self):
        # Extract and execute ONLY the PowerShell function against in-memory
        # fake COM objects. Do not run the installer or modify the real Desktop.
        escaped=str(SCRIPT).replace("'", "''")
        code=r"""
$ErrorActionPreference='Stop'
$tokens=$null; $errors=$null
$tree=[System.Management.Automation.Language.Parser]::ParseFile(
    '<SCRIPT>',[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw 'INSTALLER_PARSE_FAILED' }
$def=$tree.Find({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -eq 'Write-EveWidgetShortcut'
},$true)
if ($null -eq $def) { throw 'SHORTCUT_FUNCTION_MISSING' }
Invoke-Expression $def.Extent.Text
$script:fakeLink=[pscustomobject]@{
    TargetPath='';Arguments='';WorkingDirectory='';
    Description='';IconLocation=''
}
$script:fakeLink | Add-Member -MemberType ScriptMethod -Name Save -Value {}
$script:fakeShell=[pscustomobject]@{}
$script:fakeShell | Add-Member -MemberType ScriptMethod -Name CreateShortcut -Value {
    param($destination)
    return $script:fakeLink
}
$shell=$script:fakeShell
$pythonw='C:\fake\pythonw.exe'
$repo='C:\fake'
$line='-m v4.desktop_widget --data-root "C:\Users\test\EVE-V4-Data"'
Write-EveWidgetShortcut -Destination 'C:\fake.lnk' -ArgumentLine $line
if ($script:fakeLink.Arguments -isnot [string]) { throw 'ARGUMENTS_NOT_STRING' }
if ($script:fakeLink.Arguments -cne $line) { throw 'ARGUMENTS_NOT_PRESERVED' }
if ($script:fakeLink.TargetPath -cne $pythonw) { throw 'BAD_TARGET' }
Write-Output 'FAKE_SHORTCUT_ARGUMENTS_OK'
""".replace("<SCRIPT>",escaped)
        proc=subprocess.run(["powershell.exe","-NoProfile","-NonInteractive",
                             "-Command",code],capture_output=True,text=True,
                            timeout=20,check=False)
        self.assertEqual(proc.returncode,0,(proc.stdout+"\n"+proc.stderr)[-2000:])
        self.assertIn("FAKE_SHORTCUT_ARGUMENTS_OK",proc.stdout)


if __name__=="__main__":
    unittest.main()
