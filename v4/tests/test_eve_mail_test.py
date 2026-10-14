"""The V4 game-mail diagnostic cannot leak credentials or send on import."""
from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from v4.eve_mail_test import (
    ESI_IDS_URL, WORKER_URL, GameMailTestError, run_test, main,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code, self.payload = status_code, payload

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, *, health=(200, None), ids=(200, None), send=(200, None)):
        self.responses = [health, ids, send]
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        status, data = self.responses.pop(0)
        return FakeResponse(status, data or {})


class GameMailManualTests(unittest.TestCase):
    KEY = "M" * 48

    def good_session(self, *, health=None, ids=None, send=None):
        return FakeSession(
            health=(200, health if health is not None else {
                "ok":True, "sender_id": 12345, "sender_name":"LadyGuaGua"}),
            ids=(200, ids if ids is not None else {
                "characters":[{"id":67890,"name":"MikeChong"}]}),
            send=(200, send if send is not None else {
                "ok":True,"mail_id":234567,"sender_id":12345,
                "recipient_id":67890}))

    def test_one_explicit_mail_and_no_esi_secret(self):
        session=self.good_session()
        stamp=datetime(2026,10,14,11,3,tzinfo=timezone.utc)
        response=run_test("MikeChong",session=session,get_key=lambda:self.KEY,
                          now=stamp,idempotency="test987")
        self.assertTrue(response["sent"])
        self.assertEqual(response["status"],"EVE_GAME_MAIL_TEST_SENT")
        self.assertEqual(response["sender_name"],"LadyGuaGua")
        self.assertEqual(response["recipient"],"MikeChong")
        self.assertEqual(response["mail_id"],234567)
        self.assertEqual(len(session.calls),3)
        health, ids, sent=session.calls
        self.assertEqual(health[0:2],("GET", WORKER_URL+"/api/mail-health"))
        self.assertEqual(ids[0:2],("POST", ESI_IDS_URL))
        self.assertNotIn("Authorization",ids[2]["headers"])
        self.assertEqual(sent[0:2],("POST", WORKER_URL+"/api/send-mail"))
        self.assertEqual(sent[2]["json"]["recipient_id"],67890)
        self.assertEqual(sent[2]["json"]["idempotency_key"],
                         "v4-one-shot-test:test987")
        self.assertIn("非",sent[2]["json"]["body"])
        self.assertNotIn(self.KEY, str(sent[2]["json"]))
        self.assertEqual(health[2]["headers"]["Authorization"],"Bearer "+self.KEY)
        self.assertNotIn(self.KEY,json.dumps(response,ensure_ascii=False))
        self.assertFalse(response["formal_opportunities_enabled"])
        self.assertFalse(response["local_scanner_modified"])

    def test_sender_health_probe_does_not_send(self):
        session=self.good_session()
        x=run_test("MikeChong",session=session,get_key=lambda:self.KEY,
                   health_only=True)
        self.assertEqual(x["status"],"EVE_GAME_MAIL_SENDER_HEALTHY")
        self.assertFalse(x["sent"])
        self.assertEqual(len(session.calls),1)

    def test_wrong_recipient_rejected_before_network(self):
        session=self.good_session()
        with self.assertRaisesRegex(GameMailTestError,"ALLOWLIST"):
            run_test("SomeoneElse",session=session,get_key=lambda:self.KEY)
        self.assertEqual(session.calls,[])

    def test_missing_bridge_secret_sends_nothing(self):
        session=self.good_session()
        with self.assertRaisesRegex(GameMailTestError,"MISSING_OR_INVALID"):
            run_test(session=session,get_key=lambda:None)
        self.assertEqual(session.calls,[])

    def test_worker_wrong_key_blocks_esi_lookup_and_send(self):
        session=self.good_session()
        session.responses[0]=(401,{})
        with self.assertRaisesRegex(GameMailTestError,"WORKER_API_KEY_MISMATCH"):
            run_test(session=session,get_key=lambda:self.KEY)
        self.assertEqual(len(session.calls),1)

    def test_worker_mail_sender_needs_reauth(self):
        session=self.good_session()
        session.responses[0]=(409,{"error":"mail_sender_not_authorized"})
        with self.assertRaisesRegex(GameMailTestError,"REAUTHORIZE"):
            run_test(session=session,get_key=lambda:self.KEY)
        self.assertEqual(len(session.calls),1)

    def test_wrong_sender_character_never_sends(self):
        session=self.good_session(health={
            "ok":True,"sender_id":987,"sender_name":"Unrelated"})
        with self.assertRaisesRegex(GameMailTestError,"UNEXPECTED_EVE_MAIL_SENDER"):
            run_test(session=session,get_key=lambda:self.KEY)
        self.assertEqual(len(session.calls),1)

    def test_missing_exact_character_id_never_sends(self):
        session=self.good_session(ids={
            "characters":[{"name":"MikeChongAlt","id":67890}]})
        with self.assertRaisesRegex(GameMailTestError,"CHARACTER_NOT_FOUND"):
            run_test(session=session,get_key=lambda:self.KEY)
        self.assertEqual(len(session.calls),2)

    def test_worker_delivery_failure_has_no_fake_success(self):
        session=self.good_session(send={"ok":False, "error":"blocked"})
        with self.assertRaisesRegex(GameMailTestError,"SEND_FAILED"):
            run_test(session=session,get_key=lambda:self.KEY)

    def test_idempotency_skip_does_not_claim_delivered(self):
        session=self.good_session(send={"ok":True,"skipped":True,
                                        "reason":"duplicate"})
        x=run_test(session=session,get_key=lambda:self.KEY)
        self.assertFalse(x["sent"])
        self.assertEqual(x["status"],"EVE_GAME_MAIL_ALREADY_SENT")

    def test_no_mail_id_does_not_claim_success(self):
        session=self.good_session(send={"ok":True})
        with self.assertRaisesRegex(GameMailTestError,"ACCEPTANCE_ID_MISSING"):
            run_test(session=session,get_key=lambda:self.KEY)

    def test_send_only_explicit_main_cli(self):
        import io
        from contextlib import redirect_stdout
        sink=io.StringIO()
        with patch("sys.argv",["v4.eve_mail_test","--recipient","MikeChong"]), \\
             patch("v4.eve_mail_test.run_test",
                   return_value={"status":"EVE_GAME_MAIL_TEST_SENT","sent":True}) as fn:
            with redirect_stdout(sink):
                main()
        self.assertEqual(fn.call_count,1)
        self.assertTrue(json.loads(sink.getvalue())["sent"])


if __name__=="__main__":
    unittest.main()
