"""Contract-only audit and review mail test fixtures without network access."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v4.contract_review import make_review
from v4.research_mail import configure, render_review, send_review, disable


class _Vault:
    def __init__(self):
        self.data = {}
    def set_password(self, service, user, secret):
        self.data[(service,user)] = secret
    def get_password(self, service, user):
        return self.data.get((service,user))


class _SMTP:
    sent = []
    def __init__(self, host, port, timeout):
        assert (host,port) == ("smtp.gmail.com",465)
    def __enter__(self):
        return self
    def __exit__(self,*args):
        pass
    def login(self, user, secret):
        assert secret == "abcdefghijklmnop"
    def send_message(self, msg):
        self.sent.append(msg)


def mock_review(**extra):
    data = {
        "run_folder":"20261014T082300Z-613afb20",
        "finished_at":"2026-10-14T08:43:00+00:00",
        "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
        "source_input_integrity":"ALL_PARSED",
        "contract_proofs_audited":2,
        "sqlite_unique_proofs":32880,
        "contract_rejection_reasons":{"LIVE_ORDER_AND_CONTRACT_NOT_REVALIDATED":1},
        "research_leads_total":1,
        "research_leads":[{
            "contract_id":123456789,"review_tier":"MODEL_CANDIDATE",
            "contract_price":100000000.0,"investment":100000000.0,
            "net_profit_snapshot":65000000.0,"roi_snapshot":0.65,
            "stress_profit_snapshot":53000000.0,
            "included_items":{"34":100},
            "expires_at":"2026-10-15T10:00:00Z",
            "source_location":60003760,
        }],
    }
    data.update(extra)
    return data


class V4ContractReviewTests(unittest.TestCase):
    def test_real_proofs_only_unverified_contracts_with_positive_stress(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root/"runs"/"20261014T082300Z-613afb20"
            folder.mkdir(parents=True)
            (folder/"manifest.json").write_text(json.dumps({
                "status":"SHADOW_RECORDED","mail_enabled":False,
                "ready_for_production":False,
                "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
                "source_input_integrity":"ALL_PARSED",
                "sqlite_unique_proofs":32880,
            }),encoding="utf-8")
            (folder/"deep_shadow.json").write_text(json.dumps({
                "status":"SHADOW_ONLY_NO_LIVE_ALERTS","contract_jita_examined":4,
            }),encoding="utf-8")
            rows=[
                {"kind":"contract","contract_id":101,"reason":"LIVE_ORDER_AND_CONTRACT_NOT_REVALIDATED",
                 "status":"WATCH","model_candidate":True,"net_profit":65000000,
                 "roi":.65,"stress_profit":50000000,"cost":100000000,
                 "contract_price":100000000,"included_items":{"34":100}},
                {"kind":"contract","contract_id":102,"reason":"BELOW_GATE_OR_STRESS",
                 "status":"WATCH","net_profit":22000000,"roi":.11,
                 "stress_profit":8000000,"cost":200000000,
                 "contract_price":200000000,"included_items":{"36":10}},
                {"kind":"contract","contract_id":103,"reason":"ITEM_CLASSIFICATION_UNVERIFIED_OR_BLUEPRINT",
                 "status":"RESEARCH","net_profit":900000000,"roi":.9,
                 "stress_profit":800000000,"cost":100000000,
                 "included_items":{"400":1}},
                {"kind":"contract","contract_id":104,"reason":"BELOW_GATE_OR_STRESS",
                 "status":"WATCH","net_profit":0,"roi":0,"cost":10000000,
                 "stress_profit":0,"included_items":{"36":1}},
                {"kind":"market","status":"WATCH","reason":"BELOW_GATE_OR_STRESS","net_profit":100000000},
            ]
            (folder/"all_proofs.jsonl").write_text(
                "".join(json.dumps(row)+"\n" for row in rows),encoding="utf-8")
            review=make_review(root)
            self.assertEqual(review["contract_proofs_audited"],4)
            self.assertEqual(review["research_leads_total"],2)
            self.assertEqual([p["contract_id"] for p in review["research_leads"]],[101,102])
            self.assertFalse(review["research_leads"][0]["live_verified"])
            self.assertFalse(review["research_leads"][0]["actionable"])
            self.assertEqual(review["contract_rejection_reasons"]
                ["ITEM_CLASSIFICATION_UNVERIFIED_OR_BLUEPRINT"],1)

    def test_incomplete_source_does_not_email_candidates(self):
        subject,body=render_review(mock_review(
            coverage_gate="PARTIAL_UNVERIFIED"))
        self.assertIn("异常",subject)
        self.assertNotIn("123456789",body)
        self.assertIn("隐藏全部合同候选",body)

    def test_digest_labels_estimated_not_live_verified(self):
        subject,body=render_review(mock_review())
        self.assertIn("非交易提醒",subject)
        self.assertIn("合同ID：123456789",body)
        self.assertIn("快照估计净利",body)
        self.assertIn("未实时核实",body)

    def test_explicit_config_send_once_and_preserve_secret(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            vault=_Vault()
            _SMTP.sent=[]
            x=configure(root,"example@gmail.com","example@gmail.com",
                        "abcd efgh ijkl mnop",vault=vault)
            self.assertFalse(x["secret_printed"])
            with patch("v4.research_mail.make_review",return_value=mock_review()):
                sent=send_review(root,
                     expected_run="20261014T082300Z-613afb20",
                     vault=vault,smtp_factory=_SMTP)
                skipped=send_review(root,
                     expected_run="20261014T082300Z-613afb20",
                     vault=vault,smtp_factory=_SMTP)
            self.assertTrue(sent["sent"])
            self.assertFalse(skipped["sent"])
            self.assertEqual(len(_SMTP.sent),1)
            self.assertIn("合同ID：123456789",_SMTP.sent[0].get_content())
            receipt=(root/"mail-review"/"receipts"/
                     "20261014T082300Z-613afb20.json").read_text("utf-8")
            self.assertNotIn("abcdefghijklmnop",receipt)
            self.assertNotIn("abcdefghijklmnop",
                (root/"config"/"research_gmail.json").read_text("utf-8"))
            disabled=disable(root)
            self.assertFalse(disabled["research_mail_enabled"])
            self.assertEqual(send_review(root)["status"],"REVIEW_GMAIL_DISABLED")

    def test_rejects_unrelated_scan_or_unset_vault(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            vault=_Vault()
            configure(root,"example@gmail.com","example@gmail.com",
                      "abcdefghijklmnop",vault=vault)
            with patch("v4.research_mail.make_review",return_value=mock_review()):
                with self.assertRaisesRegex(RuntimeError,"LATEST_COMPLETED_RUN_NOT_CURRENT"):
                    send_review(root,expected_run="wrong_run",vault=vault,smtp_factory=_SMTP)
                with self.assertRaisesRegex(RuntimeError,"REVIEW_GMAIL_VAULT_SECRET_MISSING"):
                    send_review(root,vault=_Vault(),smtp_factory=_SMTP)


if __name__=="__main__":
    unittest.main()
