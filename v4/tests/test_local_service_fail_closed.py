"""Safety regression: never send a normal digest from incomplete structures.

No ESI, Gmail, game mail, credential access, or scan job is executed by tests.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v4.local_service import execute, main


class FailClosedTests(unittest.TestCase):
    def test_degraded_scan_keeps_diagnostic_reasons(self):
        def scan(root):
            return {
                "status": "SHADOW_RECORDED",
                "mail_enabled": False,
                "run_folder": str(root / "runs" / "one"),
                "coverage_gate": "PARTIAL_UNVERIFIED",
                "source_input_integrity": "ALL_PARSED",
                "structure_health": {
                    "four_h": {"status": "FAILED", "reason": "NONRETRYABLE_REQUEST",
                               "failed_page": 1, "pages_fetched": 0},
                    "cj": {"status": "FAILED", "reason": "TRANSIENT_EXHAUSTED",
                           "failed_page": 2, "pages_fetched": 1,
                           "transient_retries": 4},
                    "o4t": {"status": "COMPLETE", "pages": 1, "pages_fetched": 1}
                },
            }
        with tempfile.TemporaryDirectory() as td:
            with patch("v4.local_service.storage_check",
                       return_value={"free_gib": 100, "enough_space": True}), \
                 patch("v4.local_service.backup_due", return_value=False):
                result = execute(Path(td), scanner=scan)
        self.assertEqual(result["status"], "DEGRADED_PARTIAL_COVERAGE")
        self.assertEqual(result["failed_structure_diagnostics"]["four_h"]["reason"],
                         "NONRETRYABLE_REQUEST")
        self.assertEqual(result["failed_structure_diagnostics"]["cj"]["failed_page"], 2)
        self.assertNotIn("o4t", result["failed_structure_diagnostics"])

    def test_incomplete_digest_subject_is_explicit_outage_not_zero_profit(self):
        from v4.unified_review import render, render_html
        review = {
            "run_folder": "20261020T152301Z-fixture",
            "coverage_gate": "PARTIAL_UNVERIFIED",
            "source_input_integrity": "ALL_PARSED",
            "structure_health": {
                "four_h": "FAILED", "cj": "FAILED", "o4t": "COMPLETE"
            },
            "market_research_leads": [{"type_id": 1}],
        }
        subject, body = render(review)
        html_subject, html_body = render_html(review)
        game_subject, game_body = render(review, game=True)
        self.assertEqual(subject, html_subject)
        self.assertEqual(subject, game_subject)
        self.assertIn("V4采集故障", subject)
        self.assertIn("4-H", subject)
        self.assertIn("C-J", subject)
        self.assertNotIn("市场0", subject)
        self.assertIn("机会判断已暂停", subject)
        self.assertIn("不是零机会", body)
        self.assertIn("不是零机会", html_body)
        self.assertIn("不是零机会", game_body)
        self.assertNotIn("商品", body)


    def test_degraded_job_retains_warning_delivery_but_nonzero_task_status(self):
        degraded = {
            "status": "DEGRADED_PARTIAL_COVERAGE",
            "run_folder_name": "20261020T152301Z-fixture",
            "structure_status": {k: "FAILED" for k in ("four_h", "cj", "o4t")},
            "failed_structure_diagnostics": {
                k: {"reason": "NONRETRYABLE_REQUEST"}
                for k in ("four_h", "cj", "o4t")
            }
        }
        with tempfile.TemporaryDirectory() as td:
            resolved_root = Path(td).resolve()  # Windows 8.3 aliases differ.
            with patch.object(sys, "argv",
                              ["v4.local_service", "--data-root", td]), \
                 patch("v4.local_service.execute", return_value=degraded), \
                 patch("v4.research_mail.send_review",
                       return_value={"status": "REVIEW_GMAIL_SENT",
                                     "sent": True}) as gmail, \
                 patch("v4.game_mail_review.send_review_to_game",
                       return_value={"status": "V4_GAME_RESEARCH_MAIL_BATCH_SENT",
                                     "recipient_failure_count": 0}) as game:
                code = main()
            logfile = (Path(td) / "logs" / "shadow-task.log").read_text(encoding="utf8")
        self.assertEqual(code, 2)
        self.assertIn("REVIEW_MAIL_WARNING INCOMPLETE_SOURCE_COVERAGE", logfile)
        self.assertIn("failed_structure_diagnostics", logfile)
        gmail.assert_called_once_with(
            resolved_root, expected_run="20261020T152301Z-fixture")
        game.assert_called_once_with(
            resolved_root, expected_run="20261020T152301Z-fixture")


if __name__ == "__main__":
    unittest.main()
