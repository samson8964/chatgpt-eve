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

    def test_degraded_job_sends_neither_gmail_nor_game_mail(self):
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
            with patch.object(sys, "argv",
                              ["v4.local_service", "--data-root", td]), \
                 patch("v4.local_service.execute", return_value=degraded), \
                 patch("v4.research_mail.send_review") as gmail, \
                 patch("v4.game_mail_review.send_review_to_game") as game:
                code = main()
            logfile = (Path(td) / "logs" / "shadow-task.log").read_text(encoding="utf8")
        self.assertEqual(code, 2)
        self.assertIn("REVIEW_MAIL_SKIPPED INCOMPLETE_SOURCE_COVERAGE", logfile)
        self.assertIn("failed_structure_diagnostics", logfile)
        gmail.assert_not_called()
        game.assert_not_called()


if __name__ == "__main__":
    unittest.main()
