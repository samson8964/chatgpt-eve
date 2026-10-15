"""Read-only history comparison: file freshness is NOT candidate freshness."""
import json
import tempfile
import unittest
from pathlib import Path

from v4.freshness_audit import inspect


class FreshnessAuditTests(unittest.TestCase):
    def write_run(self, root, name, *, market_sha, contract_sha,
                  market_ts, contract_ts, profit, other=False):
        folder = root/"runs"/name
        folder.mkdir(parents=True)
        (folder/"manifest.json").write_text(
            json.dumps({"status":"SHADOW_RECORDED"}),encoding="utf-8")
        (folder/"full_market_report.json").write_text(json.dumps({
            "overall":"CENSUS_COMPLETE_PROOFS_NOT_READY",
            "sources":{
                "market_orders":{
                    "status":"COMPLETE","sha256":market_sha,
                    "last_modified":market_ts,"age_hours":0.25},
                "public_contracts":{
                    "status":"COMPLETE","sha256":contract_sha,
                    "last_modified":contract_ts,"age_hours":0.75},
            }}),encoding="utf-8")
        (folder/"deep_shadow.json").write_text(json.dumps({
            "structure_health":{
                "four_h":{"status":"COMPLETE","orders":150},
                "cj":{"status":"COMPLETE","orders":85},
                "o4t":{"status":"COMPLETE","orders":45}}}),encoding="utf-8")
        proofs=[
            {"kind":"market","model_candidate":True,"source_location":1,
             "type_id":34,"profit":profit},
            {"kind":"contract","model_candidate":True,
             "contract_id":777,"net_profit":50000000},
        ]
        if other:
            proofs.append({"kind":"market","model_candidate":True,
                           "source_location":1,"type_id":35,"profit":25000000})
        (folder/"all_proofs.jsonl").write_text(
            "".join(json.dumps(x)+"\n" for x in proofs),encoding="utf-8")

    def test_sha_changes_even_if_candidates_stay_same(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.write_run(root,"20261015T012300Z-first",market_sha="abc",
                           contract_sha="def",market_ts="2026-10-15T01:20:00Z",
                           contract_ts="2026-10-15T01:15:00Z",profit=60000000)
            self.write_run(root,"20261015T032300Z-second",market_sha="ghi",
                           contract_sha="def",market_ts="2026-10-15T03:20:00Z",
                           contract_ts="2026-10-15T01:15:00Z",profit=60000000)
            output=inspect(root,last=8)
            self.assertEqual(output["runs_compared"],2)
            last=output["history"][-1]
            self.assertTrue(last["market"]["changed_from_previous_run"])
            self.assertFalse(last["contracts"]["changed_from_previous_run"])
            self.assertTrue(last["market"]["source_timestamp_changed"])
            self.assertEqual(last["candidate_diff"]["retained_profit_unchanged"],2)
            self.assertEqual(last["structures"]["cj"]["order_rows"],85)
            self.assertIsNone(last["structures"]["cj"]["esi_order_book_sha256"])
            self.assertNotIn("abc",str(output))
            self.assertNotIn("ghi",str(output))

    def test_candidate_change_not_sufficient_for_source_date_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.write_run(root,"20261015T012300Z-first",market_sha="abc",
                           contract_sha="def",market_ts="2026-10-15T01:20:00Z",
                           contract_ts="2026-10-15T01:15:00Z",profit=60000000)
            self.write_run(root,"20261015T032300Z-second",market_sha="abc",
                           contract_sha="new",market_ts="2026-10-15T01:20:00Z",
                           contract_ts="2026-10-15T03:15:00Z",profit=70000000,
                           other=True)
            last=inspect(root,last=3)["history"][-1]
            self.assertFalse(last["market"]["changed_from_previous_run"])
            self.assertTrue(last["contracts"]["changed_from_previous_run"])
            self.assertEqual(last["candidate_diff"]["new"],1)
            self.assertEqual(last["candidate_diff"]["retained_profit_changed"],1)
            self.assertEqual(last["candidate_diff"]["retained_profit_unchanged"],1)

    def test_invalid_limits_and_absent_scans(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(inspect(Path(temp))["status"],"NO_LOCAL_RUNS")
            with self.assertRaises(ValueError):
                inspect(Path(temp),last=0)


if __name__=="__main__":
    unittest.main()
