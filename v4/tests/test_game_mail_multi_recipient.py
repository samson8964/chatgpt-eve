"""V4 two-recipient research mail: isolated EVE ID, delivery and receipts."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v4.game_mail_review import (
    add_recipient, replace_retired_recipient, enable, read_settings, send_review_to_game,
    GameMailTestError, EXPECTED_SENDER_ID, ALLOWED_RECIPIENTS,
)


class Response:
    def __init__(self, status, body):
        self.status_code=status
        self.body=body
    def json(self):
        return self.body


class Transport:
    def __init__(self, *, fail_lady=False):
        self.calls=[]
        self.fail_lady=fail_lady
    def request(self, method, url, **kwargs):
        self.calls.append((method,url,kwargs))
        if url.endswith("/api/mail-health"):
            return Response(200, {"ok":True,"sender_name":"LadyGuaGua",
                                  "sender_id":EXPECTED_SENDER_ID})
        if url.endswith("/api/send-mail"):
            rid=kwargs["json"]["recipient_id"]
            if rid==987654321 and self.fail_lady:
                return Response(502,{"ok":False})
            return Response(200,{"ok":True,"sender_id":EXPECTED_SENDER_ID,
                                 "recipient_id":rid,"mail_id":403312125+len(self.calls)})
        raise AssertionError("Unexpected network call")


def review():
    return {
        "run_folder":"20261014T134500Z-candidate",
        "contract_pricing_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT",
        "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
        "source_input_integrity":"ALL_PARSED",
        "research_leads_total":0,
        "research_leads":[],
        "market_research_leads":[],
        "contract_research_leads":[],
    }


class TwoRecipientTests(unittest.TestCase):
    SECRET="A"*48

    def test_add_lady_preserves_mike_and_does_not_send(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            enable(root)
            output=add_recipient(root,recipient="LadyBaBa",
                                 resolver=lambda name:987654321)
            self.assertEqual(output["status"],"V4_GAME_RECIPIENT_ADDED")
            self.assertFalse(output["sent"])
            self.assertEqual(output["recipients"],["MikeChong","LadyBaBa"])
            config=read_settings(root)
            self.assertEqual(config["schema"],2)
            self.assertEqual(config["recipients"],[
                {"name":"MikeChong","id":ALLOWED_RECIPIENTS["MikeChong"]},
                {"name":"LadyBaBa","id":987654321},
            ])
            self.assertNotIn(self.SECRET,(root/"config"/"eve_game_mail_review.json").read_text("utf-8"))
            again=add_recipient(root,recipient="LadyBaBa",
                                 resolver=lambda _:1)
            self.assertEqual(again["status"],"V4_GAME_RECIPIENT_ALREADY_ENABLED")
            self.assertEqual(read_settings(root)["recipients"],config["recipients"])
            old_command=enable(root,recipient="MikeChong")
            self.assertEqual(old_command["status"],
                             "V4_GAME_RESEARCH_MAIL_ALREADY_ENABLED")
            self.assertEqual(read_settings(root)["recipients"],config["recipients"])

    def test_real_exact_name_esi_lookup_not_user_guessed(self):
        class FakeESI:
            def request(self,method,url,**kwargs):
                self.calls=(method,url,kwargs)
                return Response(200,{"characters":[{"name":"LadyBaBa","id":987654321}]})
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            enable(root)
            esi=FakeESI()
            result=add_recipient(root,recipient="LadyBaBa",session=esi)
            self.assertEqual(result["recipient_id"],987654321)
            self.assertIn("/universe/ids/",esi.calls[1])
            self.assertNotIn("Authorization",esi.calls[2]["headers"])

    def test_unrecognized_name_keeps_prior_config_untouched(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            enable(root)
            current=(root/"config"/"eve_game_mail_review.json").read_bytes()
            with self.assertRaisesRegex(GameMailTestError,"CHARACTER_NOT_FOUND"):
                add_recipient(root,recipient="LadyBaBa",
                              resolver=lambda _: (_ for _ in ()).throw(
                                  GameMailTestError("ESI_CHARACTER_NOT_FOUND")))
            self.assertEqual(current,(root/"config"/"eve_game_mail_review.json").read_bytes())
            with self.assertRaisesRegex(ValueError,"NOT_ALLOWED"):
                add_recipient(root,recipient="RandomPilot")
            self.assertEqual(current,(root/"config"/"eve_game_mail_review.json").read_bytes())

    def test_one_scan_sends_both_only_once(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            enable(root)
            add_recipient(root,resolver=lambda _:987654321)
            network=Transport()
            with patch("v4.game_mail_review.make_review",return_value=review()):
                first=send_review_to_game(root,session=network,get_key=lambda:self.SECRET)
                second=send_review_to_game(root,session=network,get_key=lambda:self.SECRET)
            self.assertEqual(first["status"],"V4_GAME_RESEARCH_MAIL_BATCH_SENT")
            self.assertEqual(first["recipient_success_count"],2)
            self.assertEqual(first["recipient_failure_count"],0)
            self.assertEqual(second["status"],"V4_GAME_RESEARCH_MAIL_BATCH_ALREADY_SENT")
            self.assertEqual(sum(call[1].endswith("/api/send-mail")
                                 for call in network.calls),2)
            first_receipt=root/"mail-review"/"eve-receipts"/(review()["run_folder"]+".json")
            lady_receipt=root/"mail-review"/"eve-receipts"/(
                review()["run_folder"]+"-987654321.json")
            self.assertTrue(first_receipt.is_file())
            self.assertTrue(lady_receipt.is_file())
            self.assertEqual(json.loads(first_receipt.read_text("utf-8"))["recipient"],"MikeChong")
            self.assertEqual(json.loads(lady_receipt.read_text("utf-8"))["recipient"],"LadyBaBa")
            self.assertNotIn(self.SECRET,str(first))
            self.assertNotIn(self.SECRET,str(second))

    def test_existing_legacy_mike_receipt_is_respected_when_adding_lady(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            enable(root)
            old=root/"mail-review"/"eve-receipts"/(review()["run_folder"]+".json")
            old.parent.mkdir(parents=True)
            old.write_text('{"schema":1,"recipient_id":2124493042}',encoding="utf-8")
            add_recipient(root,resolver=lambda _:987654321)
            network=Transport()
            with patch("v4.game_mail_review.make_review",return_value=review()):
                result=send_review_to_game(root,session=network,get_key=lambda:self.SECRET)
            self.assertEqual(result["recipients"]["MikeChong"]["status"],
                             "V4_GAME_RESEARCH_MAIL_ALREADY_SENT")
            self.assertTrue(result["recipients"]["LadyBaBa"]["sent"])
            self.assertEqual(sum(call[1].endswith("/api/send-mail")
                                 for call in network.calls),1)
            self.assertEqual(old.read_text("utf-8"),'{"schema":1,"recipient_id":2124493042}')

    def test_failure_of_lady_does_not_prevent_mike_or_fake_full_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            enable(root)
            add_recipient(root,resolver=lambda _:987654321)
            bad=Transport(fail_lady=True)
            with patch("v4.game_mail_review.make_review",return_value=review()):
                first=send_review_to_game(root,session=bad,get_key=lambda:self.SECRET)
                second=send_review_to_game(
                    root,session=Transport(),get_key=lambda:self.SECRET)
            self.assertEqual(first["status"],"V4_GAME_RESEARCH_MAIL_PARTIAL_FAILURE")
            self.assertEqual(first["recipient_failure_count"],1)
            self.assertTrue(first["recipients"]["MikeChong"]["sent"])
            self.assertFalse(first["recipients"]["LadyBaBa"]["sent"])
            self.assertEqual(second["recipients"]["MikeChong"]["status"],
                             "V4_GAME_RESEARCH_MAIL_ALREADY_SENT")
            self.assertTrue(second["recipients"]["LadyBaBa"]["sent"])


    def test_migrate_retired_lady_to_abr_preserves_mike_and_receipts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            enable(root)
            add_recipient(root, recipient="LadyBaBa", resolver=lambda _: 987654321)
            prior = root / "mail-review" / "eve-receipts" / (
                review()["run_folder"] + "-987654321.json")
            prior.parent.mkdir(parents=True)
            prior.write_text('{"recipient":"LadyBaBa","sent":true}', encoding="utf-8")
            captured = []
            result = replace_retired_recipient(
                root, resolver=lambda name: (
                    captured.append(name) or 2124888999))
            self.assertEqual(captured, ["Abr Hunter"])
            self.assertEqual(result["status"], "V4_GAME_RETIRED_RECIPIENT_REPLACED")
            self.assertFalse(result["sent"])
            self.assertEqual([r["name"] for r in read_settings(root)["recipients"]],
                             ["MikeChong", "Abr Hunter"])
            self.assertEqual(read_settings(root)["recipients"][1]["id"], 2124888999)
            self.assertTrue(prior.exists())
            self.assertEqual(replace_retired_recipient(root)["status"],
                             "V4_GAME_RECIPIENT_ALREADY_REPLACED")

            network = Transport()
            with patch("v4.game_mail_review.make_review", return_value=review()):
                sent = send_review_to_game(root, session=network,
                                           get_key=lambda:self.SECRET)
            ids = [c[2]["json"]["recipient_id"] for c in network.calls
                   if c[1].endswith("/api/send-mail")]
            self.assertEqual(ids, [ALLOWED_RECIPIENTS["MikeChong"], 2124888999])
            self.assertEqual(sent["recipient_failure_count"], 0)
            self.assertEqual(prior.read_text("utf-8"),
                             '{"recipient":"LadyBaBa","sent":true}')
            abr_receipt = root / "mail-review" / "eve-receipts" / (
                review()["run_folder"] + "-2124888999.json")
            self.assertTrue(abr_receipt.is_file())

    def test_migrate_fails_closed_and_preserves_config(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            enable(root)
            add_recipient(root, recipient="LadyBaBa", resolver=lambda _:987654321)
            cfg = root / "config" / "eve_game_mail_review.json"
            before = cfg.read_bytes()
            for resolver in (
                lambda name: 0,
                lambda name: 987654321,
                lambda name: (_ for _ in ()).throw(
                    GameMailTestError("ESI_CHARACTER_NOT_FOUND")),
            ):
                with self.assertRaises(GameMailTestError):
                    replace_retired_recipient(root, resolver=resolver)
                self.assertEqual(cfg.read_bytes(), before)
            with self.assertRaisesRegex(ValueError, "REPLACEMENT_NOT_ALLOWED"):
                replace_retired_recipient(root, recipient="Other")
            self.assertEqual(cfg.read_bytes(), before)

    def test_migrate_exact_name_via_public_esi_and_mike_only_setup(self):
        class FakeESI:
            def request(self, method, url, **kwargs):
                self.called = (method, url, kwargs)
                return Response(200, {"characters":[
                    {"name":"Abr Hunter","id":2124888999}]})
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(GameMailTestError, "NOT_ENABLED"):
                replace_retired_recipient(root, resolver=lambda _:2124888999)
            enable(root)
            esi = FakeESI()
            result = replace_retired_recipient(root, session=esi)
            self.assertEqual(result["status"],"V4_GAME_NEW_RECIPIENT_ADDED")
            self.assertEqual(result["recipients"],["MikeChong","Abr Hunter"])
            self.assertIn("/universe/ids/",esi.called[1])
            self.assertEqual(esi.called[2]["json"], ["Abr Hunter"])
            self.assertNotIn("Authorization",esi.called[2]["headers"])

    def test_invalid_sender_id_or_recipient_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            enable(root)
            add_recipient(root,resolver=lambda _:987654321)
            cfg=root/"config"/"eve_game_mail_review.json"
            data=json.loads(cfg.read_text("utf-8"))
            data["recipients"][0]["id"]=111
            cfg.write_text(json.dumps(data),encoding="utf-8")
            with self.assertRaisesRegex(GameMailTestError,"CONFIG_INVALID"):
                read_settings(root)


if __name__=="__main__":
    unittest.main()
