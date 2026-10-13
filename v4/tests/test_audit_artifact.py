import json
import tempfile
import unittest
from pathlib import Path

from v4.audit_artifact import audit


class ArtifactIntegrityTests(unittest.TestCase):
    def test_consistent_quota_paused_shadow_is_valid(self):
        self.check()

    def check(self, tamper=None, error=None):
        rows=[{"instance":"contract:10001","status":"RESEARCH","reason":"BLUEPRINT"},
              {"instance":"market:0001","status":"WATCH","reason":"NOT_LIVE","model_candidate":True}]
        report={"status":"SHADOW_ONLY_NO_LIVE_ALERTS","formal_candidates":0,
                "run_id":"v4-test-001","proof_count":2,"model_candidates":1,
                "reason_counts":{"BLUEPRINT":1,"NOT_LIVE":1}}
        if tamper:tamper(rows,report)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"proofs.jsonl"
            r=Path(d)/"report.json"
            p.write_text("\n".join(json.dumps(x) for x in rows)+"\n",encoding="utf-8")
            r.write_text(json.dumps(report),encoding="utf-8")
            if error:
                with self.assertRaisesRegex(ValueError,error):
                    audit(r,p)
            else:
                result=audit(r,p)
                self.assertEqual(result["proof_count"],2)
                self.assertIsNone(result["sql_unique_proofs"])
                self.assertFalse(result["durable_ledger_accepted"])

    def test_duplicate_order_proof_fails(self):
        self.check(lambda rows,report: rows.__setitem__(1,{**rows[1],"instance":"contract:10001"}),
                   "DUPLICATE_PROOF_INSTANCE")

    def test_missing_reason_fails(self):
        self.check(lambda rows,report: rows[0].pop("reason"),"MISSING_PROOF_REASON")

    def test_mismatched_funnel_fails(self):
        self.check(lambda rows,report: report.update(reason_counts={"BLUEPRINT":2}),
                   "SHADOW_REJECTION_FUNNEL_MISMATCH")

    def test_mail_status_fails(self):
        self.check(lambda rows,report: rows[0].update(status="MAIL"),"UNSAFE_SHADOW_STATUS")

    def test_candidate_count_fails(self):
        self.check(lambda rows,report: report.update(model_candidates=0),"SHADOW_MODEL_CANDIDATE_MISMATCH")


if __name__=="__main__":
    unittest.main()
