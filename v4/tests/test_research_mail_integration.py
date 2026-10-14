"""Windowless scheduled V4 scan reports email separately, even on failure."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v4.local_service import main


class ResearchEmailIntegrationTests(unittest.TestCase):
    def invoke(self, root, scan, sender):
        args=["v4.local_service","--data-root",str(root)]
        sending = ({"side_effect": sender} if isinstance(sender, BaseException)
                   else {"return_value": sender})
        with patch("sys.argv",args),patch("v4.local_service.execute",return_value=scan),\
             patch("v4.research_mail.send_review",**sending) as send:
            exit_code=main()
        log=(root/"logs"/"shadow-task.log").read_text(encoding="utf-8")
        return exit_code,log,send

    def test_success_plus_research_email_keeps_zero_exit(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            scan={"status":"SHADOW_RECORDED","run_folder_name":"run-ok"}
            code,log,send=self.invoke(root,scan,{"status":"REVIEW_GMAIL_SENT","sent":True})
            self.assertEqual(code,0)
            self.assertIn("REVIEW_GMAIL",log)
            self.assertIn("SHADOW_RECORDED",log)
            self.assertEqual(send.call_args.kwargs["expected_run"],"run-ok")

    def test_mail_error_is_explicit_exit_three_not_scan_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            scan={"status":"SHADOW_RECORDED","run_folder_name":"run-ok"}
            code,log,_=self.invoke(root,scan,RuntimeError("SMTP_NOT_AVAILABLE"))
            self.assertEqual(code,3)
            self.assertIn("REVIEW_MAIL_FAILED RuntimeError",log)
            self.assertIn("RESULT",log)
            self.assertNotIn("\nFAILED RuntimeError",log)
            self.assertNotIn("SMTP_NOT_AVAILABLE",log)

    def test_scan_degradation_still_returns_two_if_mail_success(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            scan={"status":"DEGRADED_INPUT_QUARANTINE","run_folder_name":"run-bad"}
            code,log,_=self.invoke(root,scan,{"status":"REVIEW_GMAIL_SENT","sent":True})
            self.assertEqual(code,2)
            self.assertIn("DEGRADED_INPUT_QUARANTINE",log)

    def test_gmail_failure_does_not_suppress_game_mail(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            scan={"status":"SHADOW_RECORDED","run_folder_name":"run-ok"}
            with (
                patch("sys.argv", ["v4.local_service","--data-root",str(root)]),
                patch("v4.local_service.execute",return_value=scan),
                patch("v4.research_mail.send_review",
                      side_effect=RuntimeError("SMTP_FAILURE")),
                patch("v4.game_mail_review.send_review_to_game",
                      return_value={"status":"V4_GAME_RESEARCH_MAIL_SENT","sent":True}) as game,
            ):
                code=main()
            log=(root/"logs"/"shadow-task.log").read_text(encoding="utf-8")
            self.assertEqual(code,3)
            self.assertIn("REVIEW_MAIL_FAILED RuntimeError",log)
            self.assertIn("GAME_REVIEW_MAIL",log)
            self.assertEqual(game.call_count,1)
            self.assertEqual(game.call_args.kwargs["expected_run"],"run-ok")
            self.assertNotIn("SMTP_FAILURE",log)

    def test_game_mail_failure_does_not_suppress_gmail(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            scan={"status":"SHADOW_RECORDED","run_folder_name":"run-ok"}
            with (
                patch("sys.argv", ["v4.local_service","--data-root",str(root)]),
                patch("v4.local_service.execute",return_value=scan),
                patch("v4.research_mail.send_review",
                      return_value={"status":"REVIEW_GMAIL_SENT","sent":True}) as gmail,
                patch("v4.game_mail_review.send_review_to_game",
                      side_effect=RuntimeError("WORKER_FAILURE")),
            ):
                code=main()
            log=(root/"logs"/"shadow-task.log").read_text(encoding="utf-8")
            self.assertEqual(code,3)
            self.assertIn("REVIEW_MAIL",log)
            self.assertIn("GAME_REVIEW_MAIL_FAILED RuntimeError",log)
            self.assertEqual(gmail.call_count,1)
            self.assertNotIn("WORKER_FAILURE",log)

    def test_both_mail_channels_can_report_success(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            scan={"status":"SHADOW_RECORDED","run_folder_name":"run-ok"}
            with (
                patch("sys.argv", ["v4.local_service","--data-root",str(root)]),
                patch("v4.local_service.execute",return_value=scan),
                patch("v4.research_mail.send_review",
                      return_value={"status":"REVIEW_GMAIL_SENT","sent":True}),
                patch("v4.game_mail_review.send_review_to_game",
                      return_value={"status":"V4_GAME_RESEARCH_MAIL_SENT","sent":True}),
            ):
                code=main()
            log=(root/"logs"/"shadow-task.log").read_text(encoding="utf-8")
            self.assertEqual(code,0)
            self.assertIn('GAME_REVIEW_MAIL {"status": "V4_GAME_RESEARCH_MAIL_SENT"',log)
            self.assertIn('REVIEW_MAIL {"status": "REVIEW_GMAIL_SENT"',log)



if __name__=="__main__":
    unittest.main()
