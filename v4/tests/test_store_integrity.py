"""Regression: HTTP batch acceptance is not equivalent to verified SQLite persistence."""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from v4.ingest import upload


class StoreIntegrityTests(unittest.TestCase):
    def exercise(self, response, expected_error=None):
        with tempfile.TemporaryDirectory() as d:
            report=Path(d)/"deep_shadow.json"
            rows=Path(d)/"all_proofs.jsonl"
            report.write_text(json.dumps({
                "status":"SHADOW_ONLY_NO_LIVE_ALERTS", "run_id":"v4-test-001",
                "proof_count":2, "contract_rows":50,
            }),encoding="utf-8")
            rows.write_text("\n".join(json.dumps(x) for x in [
                {"instance":"contract:10001","status":"RESEARCH"},
                {"instance":"contract:10002","status":"WATCH"},
            ])+"\n",encoding="utf-8")
            def reply(data):
                return types.SimpleNamespace(json=lambda: data, raise_for_status=lambda: None)
            fake_requests=types.SimpleNamespace(
                get=Mock(return_value=reply({"ok":True,"dispatch_enabled":False})),
                post=Mock(side_effect=[reply({"ok":True}),reply(response)]))
            with patch.dict(sys.modules, {"requests":fake_requests}):
                if expected_error:
                    with self.assertRaisesRegex(RuntimeError,expected_error):
                        upload(str(report),str(rows),"test-api-key")
                else:
                    result=upload(str(report),str(rows),"test-api-key")
                    self.assertEqual(result["stored"],2)
                    self.assertEqual(result["batches"],1)

    def test_success_requires_real_unique_sql_count(self):
        self.exercise({"ok":True,"committed":2,"stored_total":2,
                       "pending_added":0,"dispatch_enabled":False})

    def test_old_count_only_ack_is_not_accepted(self):
        self.exercise({"ok":True,"committed":2,
                       "pending_added":0,"dispatch_enabled":False},
                      "PROOF_SQL_UNIQUE_COUNT_MISMATCH")

    def test_fake_success_with_one_missing_row_is_detected(self):
        self.exercise({"ok":True,"committed":2,"stored_total":1,
                       "pending_added":0,"dispatch_enabled":False},
                      "PROOF_SQL_UNIQUE_COUNT_MISMATCH")

    def test_partial_batch_ack_is_rejected(self):
        self.exercise({"ok":True,"committed":1,"stored_total":1,
                       "pending_added":0,"dispatch_enabled":False},
                      "PROOF_BATCH_ACK_MISMATCH")


if __name__=="__main__":
    unittest.main()
