"""No-live-credentials V4 production notification control regression tests."""
from __future__ import annotations
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from v4.opportunity_push import run_once, _signature, _digest, _record_candidate, _current_opportunities
from v4.esi_private_source_jita_ab import STRUCTURES,JITA,ParityError
from v4.engine import Order

RUN="20261018T000000Z-abcd1234"
CLOCK=datetime(2026,10,18,0,0,tzinfo=timezone.utc)

def signal(station="O4T",typ=41059,profit=180e6):
    loc=STRUCTURES[station]
    d={"station":station,"station_id":loc,"type_id":typ,
       "hypothetical_model_pass":True,
       "reason":"FORMAL_GATE_PASSED","quantity":13,
       "net_profit_isk":profit,"roi":.12,"stress_profit_isk":175e6,
       "haul_isk":12e6,"source_vwap_isk":100e6,
       "jita_buy_vwap_isk":120e6,
       "source_sell_top5_mean":101e6,
       "source_sell_top5_levels":5,
       "jita_buy_top5_mean":119e6,
       "jita_buy_top5_levels":5}
    d["signal_key"]=_signature(d)
    return d

def dataset(items):
    return {"status":"FRESH_ESI_PRIVATE_MARKET_SHADOW_LEADS",
            "run":RUN,"approved_leads":items,
            "esi_jita":{"last_modified":"Sun, 18 Oct 2026 00:00:00 GMT",
                        "age_at_private_comparison_minutes":6},
            "private_order_counts":{"all_active_orders":10},
            "model_counts":{"MODEL_PASS_RESEARCH_ONLY":len(items)},
            "authenticated_structure_health":{},
            "private_fingerprints":{}}

class OpportunityPushTests(unittest.TestCase):
    def test_first_digest_and_no_duplicate_across_new_scans(self):
        with tempfile.TemporaryDirectory() as td:
            calls={"game":[],"gmail":[]}
            def send_game(**kw):
                calls["game"].append(kw)
                return {"status":"GAME_MAIL_SENT","sent":True}
            def send_gmail(**kw):
                calls["gmail"].append(kw)
                return {"status":"GMAIL_SENT","sent":True}
            c=signal()
            a,_=run_once(Path(td),now=CLOCK,build=lambda:dataset([c]),
                         send_game=send_game,send_gmail=send_gmail)
            self.assertEqual(a["qualified_model_leads"],1)
            self.assertFalse(a["production_source_switch"])
            self.assertEqual(len(calls["game"]),1)
            self.assertEqual(len(calls["gmail"]),1)
            self.assertEqual(calls["game"][0]["run_name"].split("-")[0],"esi")
            b,_=run_once(Path(td),now=CLOCK+timedelta(hours=2),
                         build=lambda:dataset([c]),
                         send_game=send_game,send_gmail=send_gmail)
            self.assertEqual(len(calls["game"]),1)
            self.assertEqual(len(calls["gmail"]),1)
            self.assertEqual(b["notification_channels"]["game"]["status"],
                             "NO_NEW_QUALIFIED_LEADS")
            c2=signal(profit=181e6)
            run_once(Path(td),now=CLOCK+timedelta(hours=4),
                     build=lambda:dataset([c2]),
                     send_game=send_game,send_gmail=send_gmail)
            self.assertEqual(len(calls["game"]),2)
            self.assertEqual(len(calls["gmail"]),2)

    def test_failed_recipient_does_not_poison_game_dedup(self):
        with tempfile.TemporaryDirectory() as td:
            calls=[]
            def game(**kw):
                calls.append(kw)
                return ({"status":"GAME_MAIL_PARTIAL_FAILURE",
                         "sent":True} if len(calls)==1 else
                         {"status":"GAME_MAIL_SENT","sent":True})
            send_gmail=lambda **kw:{"status":"GMAIL_NOT_CONFIGURED","sent":False}
            s=signal()
            run_once(Path(td),now=CLOCK,build=lambda:dataset([s]),
                     send_game=game,send_gmail=send_gmail)
            run_once(Path(td),now=CLOCK+timedelta(hours=2),
                     build=lambda:dataset([s]),
                     send_game=game,send_gmail=send_gmail)
            self.assertEqual(len(calls),2)
            self.assertEqual(calls[0]["run_name"],calls[1]["run_name"])

    def test_zero_candidates_are_not_spam(self):
        with tempfile.TemporaryDirectory() as td:
            def fail(**kw):raise AssertionError("MUST_NOT_MAIL_EMPTY")
            r,_=run_once(Path(td),now=CLOCK,
                         build=lambda:dataset([]),
                         send_game=fail,send_gmail=fail)
            self.assertEqual(r["qualified_model_leads"],0)

    def test_digest_identifies_shadow_not_live_trade(self):
        subject,body=_digest([signal()],
              {"last_modified":"2026-10-18T00:00:00+00:00",
               "age_at_private_comparison_minutes":5},game=True)
        self.assertIn("下单前复核",subject)
        self.assertIn("<url=showinfo:41059>",body)
        self.assertIn("模型估算",body)
        self.assertIn("卖5档均价",body)
        self.assertLess(len(body),9000)

    def test_incomplete_private_lane_cannot_emit_alert(self):
        with tempfile.TemporaryDirectory() as td:
            from unittest.mock import patch
            with patch("v4.opportunity_push._private_asks",
                       side_effect=ParityError("PRIVATE_STRUCTURE_LANE_FAILED")):
                def esi():
                    return {"status":"PARTIAL_REGION_TEST_ONLY",
                            "requested_region_ids":[10000002],
                            "regions":[{"status":"COMPLETE"}],
                            "run":RUN},Path(td)
                with self.assertRaisesRegex(ParityError,"LANE_FAILED"):
                    _current_opportunities(Path(td),run_esi=esi,
                        fetch_private=lambda:([],{}),catalog=object(),
                        haul_fn=lambda *_:10e6,now=CLOCK)


if __name__=="__main__":
    unittest.main()
