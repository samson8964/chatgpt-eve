import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import send_eve_mail_buy_only_multi as core_mail
import send_four_h_mail_multi as four_h_mail
import send_multi_item_buy_only_multi as multi_mail


class MailReminderPolicyTests(unittest.TestCase):
    def test_core_rank_only_change_is_suppressed(self):
        previous = [
            {"id": 1, "metric": 100.0, "roi": 0.20, "status": "SAFE", "grade": "A"},
            {"id": 2, "metric": 80.0, "roi": 0.15, "status": "SAFE", "grade": "B"},
        ]
        current = [previous[1].copy(), previous[0].copy()]
        state = pd.DataFrame([
            {
                "channel": "spot-deals",
                "signature": core_mail.POLICY_VERSION + "|" + json.dumps(previous, separators=(",", ":")),
                "updated_at": pd.Timestamp.now(tz="UTC").isoformat(),
            }
        ])
        with patch.object(core_mail, "_candidate_snapshot", return_value=current):
            self.assertTrue(core_mail._smart_top_is_unchanged(state, "spot-deals", []))

    def test_core_membership_change_triggers(self):
        previous = [
            {"id": 1, "metric": 100.0, "roi": 0.20, "status": "SAFE", "grade": "A"},
            {"id": 2, "metric": 80.0, "roi": 0.15, "status": "SAFE", "grade": "B"},
        ]
        current = [previous[0].copy(), {"id": 3, "metric": 70.0, "roi": 0.14, "status": "SAFE", "grade": "B"}]
        state = pd.DataFrame([
            {
                "channel": "spot-deals",
                "signature": core_mail.POLICY_VERSION + "|" + json.dumps(previous, separators=(",", ":")),
                "updated_at": pd.Timestamp.now(tz="UTC").isoformat(),
            }
        ])
        with patch.object(core_mail, "_candidate_snapshot", return_value=current):
            self.assertFalse(core_mail._smart_top_is_unchanged(state, "spot-deals", []))

    def test_four_h_rank_only_change_is_suppressed(self):
        with tempfile.TemporaryDirectory() as td:
            old_state = four_h_mail.STATE
            four_h_mail.STATE = Path(td)
            try:
                path = four_h_mail.state_path("four-h-market", "MikeChong")
                pd.DataFrame([
                    {"policy_version": four_h_mail.POLICY_VERSION, "rank": 1, "id": 10, "profit": 100.0, "roi": 0.20, "status": "SAFE", "grade": "A", "sent_at": pd.Timestamp.now(tz="UTC").isoformat()},
                    {"policy_version": four_h_mail.POLICY_VERSION, "rank": 2, "id": 20, "profit": 80.0, "roi": 0.15, "status": "SAFE", "grade": "B", "sent_at": pd.Timestamp.now(tz="UTC").isoformat()},
                ]).to_csv(path, index=False)
                picked = [
                    {"id": 20, "profit": 80.0, "roi": 0.15, "status": "SAFE", "grade": "B", "row": pd.Series(dtype=object)},
                    {"id": 10, "profit": 100.0, "roi": 0.20, "status": "SAFE", "grade": "A", "row": pd.Series(dtype=object)},
                ]
                self.assertTrue(four_h_mail.should_suppress("four-h-market", "MikeChong", picked))
            finally:
                four_h_mail.STATE = old_state

    def test_four_h_membership_change_is_incremental(self):
        with tempfile.TemporaryDirectory() as td:
            old_state = four_h_mail.STATE
            four_h_mail.STATE = Path(td)
            try:
                path = four_h_mail.state_path("four-h-market", "MikeChong")
                now = pd.Timestamp.now(tz="UTC").isoformat()
                pd.DataFrame([
                    {"policy_version": "fourh-v2-exec-1", "rank": 1, "id": 10, "profit": 100.0, "roi": 0.20, "status": "SAFE", "grade": "A", "sent_at": now},
                    {"policy_version": "fourh-v2-exec-1", "rank": 2, "id": 20, "profit": 80.0, "roi": 0.15, "status": "SAFE", "grade": "B", "sent_at": now},
                ]).to_csv(path, index=False)
                picked = [
                    {"id": 10, "profit": 100.0, "roi": 0.20, "status": "SAFE", "grade": "A", "row": pd.Series(dtype=object)},
                    {"id": 30, "profit": 70.0, "roi": 0.14, "status": "SAFE", "grade": "B", "row": pd.Series(dtype=object)},
                ]
                plan = four_h_mail.notification_plan("four-h-market", "MikeChong", picked)
                self.assertEqual(plan["mode"], "incremental")
                self.assertEqual([x["id"] for x in plan["added"]], [30])
                self.assertEqual([x["id"] for x in plan["changed"]], [])
                self.assertEqual([x["id"] for x in plan["removed"]], [20])
            finally:
                four_h_mail.STATE = old_state

    def test_four_h_profit_change_only_sends_changed_item(self):
        with tempfile.TemporaryDirectory() as td:
            old_state = four_h_mail.STATE
            four_h_mail.STATE = Path(td)
            try:
                path = four_h_mail.state_path("four-h-market", "MikeChong")
                now = pd.Timestamp.now(tz="UTC").isoformat()
                pd.DataFrame([
                    {"policy_version": four_h_mail.POLICY_VERSION, "rank": 1, "id": 10, "profit": 100_000_000.0, "roi": 0.20, "status": "SAFE", "grade": "A", "sent_at": now},
                    {"policy_version": four_h_mail.POLICY_VERSION, "rank": 2, "id": 20, "profit": 80_000_000.0, "roi": 0.15, "status": "SAFE", "grade": "B", "sent_at": now},
                ]).to_csv(path, index=False)
                picked = [
                    {"id": 10, "profit": 125_000_000.0, "roi": 0.20, "status": "SAFE", "grade": "A", "row": pd.Series(dtype=object)},
                    {"id": 20, "profit": 80_000_000.0, "roi": 0.15, "status": "SAFE", "grade": "B", "row": pd.Series(dtype=object)},
                ]
                plan = four_h_mail.notification_plan("four-h-market", "MikeChong", picked)
                self.assertEqual(plan["mode"], "incremental")
                self.assertEqual([x["id"] for x in plan["changed"]], [10])
                self.assertEqual(plan["added"], [])
                self.assertEqual(plan["removed"], [])
            finally:
                four_h_mail.STATE = old_state

    def test_multi_rank_only_change_is_suppressed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.csv"
            now = pd.Timestamp.now(tz="UTC").isoformat()
            pd.DataFrame([
                {"rank": 1, "contract_id": 101, "policy_version": multi_mail.POLICY_VERSION, "metric": 100.0, "roi": 0.20, "status": "SAFE", "grade": "A", "sent_at": now},
                {"rank": 2, "contract_id": 202, "policy_version": multi_mail.POLICY_VERSION, "metric": 80.0, "roi": 0.15, "status": "SAFE", "grade": "B", "sent_at": now},
            ]).to_csv(path, index=False)
            picked = [
                {"contract_id": 202, "gap": 80.0, "roi": 0.15, "row": pd.Series({"execution_status": "SAFE", "score_grade": "B"})},
                {"contract_id": 101, "gap": 100.0, "roi": 0.20, "row": pd.Series({"execution_status": "SAFE", "score_grade": "A"})},
            ]
            self.assertTrue(multi_mail.should_suppress(path, picked))


if __name__ == "__main__":
    unittest.main()
