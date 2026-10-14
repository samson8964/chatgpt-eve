"""V4 game-mail digests are opt-in, run-pinned, deduplicated, non-actionable."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v4.game_mail_review import (
    enable, disable, read_settings, send_review_to_game, compact_digest,
    GameMailTestError, WORKER_URL,
)


class Response:
    def __init__(self, code, data):
        self.status_code = code
        self.data = data
    def json(self):
        return self.data


class Transport:
    def __init__(self, *, code=200, send=None, health=None):
        self.calls = []
        self.replies = [
            Response(200, health or {"ok":True,"sender_name":"LadyGuaGua",
                                      "sender_id":2124679425}),
            Response(code, send or {"ok":True,"mail_id":403312041,
                                    "sender_id":2124679425,
                                    "recipient_id":2124493042}),
        ]
    def request(self, method, url, **kwargs):
        self.calls.append((method,url,kwargs))
        return self.replies.pop(0)


def review():
    return {
        "run_folder":"20261014T082300Z-sample",
        "contract_pricing_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT",
        "finished_at":"2026-10-14T08:24:00+00:00",
        "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
        "source_input_integrity":"ALL_PARSED",
        "contract_proofs_audited":1,
        "sqlite_unique_proofs":14,
        "research_leads_total":1,
        "contract_rejection_reasons":{},
        "research_leads":[{
            "contract_id":236977688, "review_tier":"MODEL_CANDIDATE",
            "contract_price":100000000, "investment":103000000,
            "haul_estimate_isk":3000000,
            "net_profit_snapshot":54000000,"roi_snapshot":0.52,
            "stress_profit_snapshot":42000000,
            "included_items":{"34":250},"source_location":1053970513596,
            "expires_at":"2026-10-15T10:00:00+00:00",
        }],
    }


class GameMailReviewTests(unittest.TestCase):
    KEY = "Z" * 48

    def test_disabled_by_default_does_not_read_scan_or_access_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch("v4.game_mail_review.make_review") as scan:
                result=send_review_to_game(root)
            self.assertEqual(result["status"],"V4_GAME_RESEARCH_MAIL_DISABLED")
            scan.assert_not_called()

    def test_optin_pin_only_verified_character_and_no_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaisesRegex(ValueError,"NOT_VERIFIED"):
                enable(root,recipient="Unverified")
            x=enable(root,recipient="MikeChong")
            self.assertFalse(x["sent"])
            config=read_settings(root)
            self.assertEqual(config["recipient_id"],2124493042)
            self.assertNotIn(self.KEY,(root/"config"/"eve_game_mail_review.json").read_text("utf-8"))
            self.assertIsNone(read_settings(root) if disable(root) is None else read_settings(root))

    def test_send_one_real_run_id_and_jita_basis_and_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            enable(root)
            session=Transport()
            with patch("v4.game_mail_review.make_review",return_value=review()):
                first=send_review_to_game(root, expected_run="20261014T082300Z-sample",
                                          session=session,get_key=lambda:self.KEY)
                second=send_review_to_game(root, expected_run="20261014T082300Z-sample",
                                           session=session,get_key=lambda:self.KEY)
            self.assertEqual(first["status"],"V4_GAME_RESEARCH_MAIL_SENT")
            self.assertTrue(first["sent"])
            self.assertEqual(first["mail_id"],403312041)
            self.assertEqual(second["status"],"V4_GAME_RESEARCH_MAIL_ALREADY_SENT")
            self.assertFalse(second["sent"])
            self.assertEqual(len(session.calls),2)
            health,send=session.calls
            self.assertEqual(health[0:2],("GET",WORKER_URL+"/api/mail-health"))
            self.assertEqual(send[0:2],("POST",WORKER_URL+"/api/send-mail"))
            self.assertEqual(send[2]["json"]["recipient_id"],2124493042)
            self.assertIn("不可直接买入",send[2]["json"]["subject"])
            self.assertIn("Jita",send[2]["json"]["body"])
            self.assertIn("236977688",send[2]["json"]["body"])
            self.assertIn("非正式机会",send[2]["json"]["body"])
            self.assertEqual(len(send[2]["json"]["idempotency_key"]), len("v4-contract-research:")+38)
            receipt=root/"mail-review"/"eve-receipts"/"20261014T082300Z-sample.json"
            self.assertTrue(receipt.is_file())
            self.assertNotIn(self.KEY,receipt.read_text("utf-8"))

    def test_old_price_basis_blocks_network_and_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            enable(root)
            snapshot=review()
            snapshot["contract_pricing_basis"]="SAME_LOCATION_SNAPSHOT"
            session=Transport()
            with patch("v4.game_mail_review.make_review",return_value=snapshot):
                with self.assertRaisesRegex(GameMailTestError,"NON_JITA_PRICING"):
                    send_review_to_game(root,session=session,get_key=lambda:self.KEY)
            self.assertFalse(session.calls)

    def test_expected_run_mismatch_blocks_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            enable(root)
            session=Transport()
            with patch("v4.game_mail_review.make_review",return_value=review()):
                with self.assertRaisesRegex(GameMailTestError,"LATEST_RUN_MISMATCH"):
                    send_review_to_game(root,expected_run="WRONG_RUN",
                                        session=session,get_key=lambda:self.KEY)
            self.assertFalse(session.calls)

    def test_wrong_sender_never_sends(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            enable(root)
            session=Transport(health={"ok":True,"sender_name":"SomeoneElse",
                                      "sender_id":2124679425})
            with patch("v4.game_mail_review.make_review",return_value=review()):
                with self.assertRaisesRegex(GameMailTestError,"SENDER_NOT_VERIFIED"):
                    send_review_to_game(root,session=session,get_key=lambda:self.KEY)
            self.assertEqual(len(session.calls),1)

    def test_worker_failure_does_not_record_sent(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            enable(root)
            session=Transport(code=502)
            with patch("v4.game_mail_review.make_review",return_value=review()):
                with self.assertRaisesRegex(GameMailTestError,"WORKER_REJECTED_HTTP_502"):
                    send_review_to_game(root,session=session,get_key=lambda:self.KEY)
            self.assertFalse((root/"mail-review"/"eve-receipts").exists())

    def test_duplicate_worker_ack_saved_without_claiming_new_send(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            enable(root)
            session=Transport(send={"ok":True,"skipped":True,"reason":"duplicate"})
            with patch("v4.game_mail_review.make_review",return_value=review()):
                x=send_review_to_game(root,session=session,get_key=lambda:self.KEY)
            self.assertEqual(x["status"],"V4_GAME_RESEARCH_MAIL_ALREADY_ACCEPTED")
            self.assertFalse(x["sent"])
            receipt=root/"mail-review"/"eve-receipts"/"20261014T082300Z-sample.json"
            self.assertTrue(json.loads(receipt.read_text("utf-8"))["already_accepted"])

    def test_strict_config_does_not_send_to_modified_character_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            enable(root)
            config_path=root/"config"/"eve_game_mail_review.json"
            c=json.loads(config_path.read_text("utf-8"))
            c["recipient_id"]=123
            config_path.write_text(json.dumps(c),encoding="utf-8")
            with self.assertRaisesRegex(GameMailTestError,"CONFIG_INVALID"):
                read_settings(root)

    def test_overlength_body_bounded_and_warning(self):
        oversized=review()
        oversized["contract_rejection_reasons"]={"A"*9000:123, "B"*9000:55}
        subject,body=compact_digest(oversized)
        self.assertLessEqual(len(body),9000)
        self.assertLessEqual(len(subject),180)
        self.assertIn("快照",subject)


if __name__=="__main__":
    unittest.main()
