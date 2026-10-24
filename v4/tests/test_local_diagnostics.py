import json
import tempfile
import unittest
from pathlib import Path

from v4.local_backup import backup
from v4.local_status import inspect
from v4.local_store import persist


class LocalDiagnosticsTests(unittest.TestCase):
    def test_readonly_status_and_windows_backup_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            run=root/"runs"/"20261014T010000Z-aaaa1111"
            run.mkdir(parents=True)
            (run/"manifest.json").write_text(
                json.dumps({"status":"SHADOW_RECORDED","coverage_gate":"PARTIAL_UNVERIFIED"}),
                encoding="utf-8")
            (run/"full_market_report.json").write_text(json.dumps({
                "overall":"CENSUS_COMPLETE_PROOFS_NOT_READY",
                "market":{"market_raw_rows":1584996},
                "sources":{"market_orders":{"status":"COMPLETE","age_hours":0.5}},
            }),encoding="utf-8")
            report={"run_id":"v4-local-test-001","status":"SHADOW_ONLY_NO_LIVE_ALERTS",
                    "proof_count":1,"model_candidates":0,"formal_candidates":0,
                    "reason_counts":{"UNVERIFIED":1},
                    "structure_health":{"cj":{"status":"FAILED","reason":"missing_api_key"}},
                    "source_input_integrity":"ALL_PARSED"}
            deep=run/"deep_shadow.json"
            deep.write_text(json.dumps(report),encoding="utf-8")
            proofs=run/"all_proofs.jsonl"
            proofs.write_text('{"instance":"contract:111","status":"RESEARCH","reason":"UNVERIFIED"}\n',
                              encoding="utf-8")
            persist(root/"sqlite"/"v4-shadow.sqlite3",deep,proofs)
            check=inspect(root)
            self.assertEqual(check["raw_market_orders"],1584996)
            self.assertEqual(check["sqlite_unique_proofs"],1)
            self.assertEqual(check["sqlite_integrity"],"ok")
            self.assertTrue(check["sqlite_count_matches_report"])
            self.assertEqual(check["structure_health"]["cj"]["reason"],"missing_api_key")
            self.assertFalse(check["mail_enabled"])
            saved=backup(root)
            self.assertEqual(saved["sqlite_integrity"],"ok")
            self.assertEqual(saved["scan_runs"],1)
            self.assertEqual(saved["proof_versions"],1)
            self.assertTrue(Path(saved["path"]).is_file())
        # On Windows TemporaryDirectory cleanup fails if either backup or status
        # leaks an open SQLite handle; this is an intentional cross-platform guard.


if __name__ == "__main__":
    unittest.main()
