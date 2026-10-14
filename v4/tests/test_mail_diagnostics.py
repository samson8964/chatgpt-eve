"""Private-data-free validation of the user's failed 20:23 scan diagnosis."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from v4.mail_diagnostics import inspect


class MailDiagnosticsTests(unittest.TestCase):
    def test_safe_schema_failure_code_and_snapshot_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            folder=root/"runs"/"20261014T122301Z-caf4e25e"
            folder.mkdir(parents=True)
            (folder/"manifest.json").write_text(json.dumps({
                "status":"SHADOW_RECORDED",
                "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
                "source_input_integrity":"ALL_PARSED",
            }),encoding="utf-8")
            (folder/"deep_shadow.json").write_text(json.dumps({
                "status":"SHADOW_ONLY_NO_LIVE_ALERTS",
                "contract_pricing_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT",
                "market_pricing_basis":"OLD_LOCAL_BUYS",
                "market_proofs_examined":1,
                "contract_approved_locations_examined":1,
            }),encoding="utf-8")
            (folder/"all_proofs.jsonl").write_text(json.dumps({
                "kind":"market","status":"WATCH"})+"\n",encoding="utf-8")
            output=inspect(root)
            self.assertEqual(output["review"],"BLOCKED")
            self.assertEqual(output["error_code"],
                "UNIFIED_REVIEW_REQUIRES_FRESH_JITA_MARKET_SCAN")
            self.assertEqual(output["actual_proofs"]["market"],1)
            self.assertFalse(output["gmail_receipt_exists"])
            self.assertFalse(output["eve_receipt_exists"])

    def test_unknown_exception_cannot_print_secrets_or_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            folder=root/"runs"/"20261014T122301Z-caf4e25e"
            folder.mkdir(parents=True)
            (folder/"manifest.json").write_text(
                '{"status":"SHADOW_RECORDED"}',encoding="utf-8")
            with patch("v4.mail_diagnostics.make_review",
                       side_effect=RuntimeError("supersecret-api-key")):
                response=inspect(root)
            self.assertEqual(response["error_code"],"UNCLASSIFIED_RuntimeError")
            self.assertNotIn("supersecret-api-key",str(response))


if __name__=="__main__":
    unittest.main()
