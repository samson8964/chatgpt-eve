"""Guard the approved Windows notification cadence against a two-hour regression.

Static policy checks only: no task or email is started by tests.
"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "scripts" / "install_v4_opportunity_push.ps1"


class OpportunityHourlyScheduleTests(unittest.TestCase):
    def test_hourly_and_staggered(self):
        text = INSTALL.read_text(encoding="utf-8")
        self.assertIn("New-TimeSpan -Hours 1", text)
        self.assertIn(".AddMinutes(45)", text)
        self.assertNotIn("New-TimeSpan -Hours 2", text)

    def test_existing_task_update_does_not_force_additional_run(self):
        text = INSTALL.read_text(encoding="utf-8")
        self.assertIn("Get-ScheduledTask -TaskName $task", text)
        self.assertIn("if (-not $existing)", text)
        self.assertIn("Start-ScheduledTask -TaskName $task", text)
        self.assertIn("OPPORTUNITY_PUSH_TASK_UPDATED_HOURLY_NO_EXTRA_RUN", text)

    def test_same_task_same_credentials_no_shadow_mutation(self):
        text = INSTALL.read_text(encoding="utf-8")
        self.assertIn("'EVE-V4-Opportunity-Push'", text)
        self.assertIn("WindowsIdentity]::GetCurrent().Name", text)
        self.assertIn("-LogonType Interactive", text)
        self.assertNotIn("Unregister-ScheduledTask", text)
        self.assertNotIn("EVE-V4-Shadow", text.replace(
            "Existing V4 shadow task, game-mail configuration and retired V3 remain untouched.", ""
        ))


if __name__ == "__main__":
    unittest.main()
