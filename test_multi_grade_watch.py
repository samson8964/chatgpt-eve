from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import send_multi_grade_watch as watch


class MultiGradeWatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_dir = Path(self.tmp.name) / "state"
        self.source = Path(self.tmp.name) / "watch.csv"

    def _df(self, ids):
        rows = []
        for i, cid in enumerate(ids):
            rows.append({
                "contract_id": cid,
                "score_grade": "A" if i % 2 == 0 else "S",
                "opportunity_score": 75 + i,
                "execution_status": "SAFE",
                "watch_class": "即时兑现",
                "contract_price": 10_000_000,
                "watch_net_profit": 20_000_000,
                "watch_roi": 0.20,
                "stress_net_profit": 15_000_000,
                "buy_unit_coverage": 1.0,
                "formal_qualified": False,
            })
        return pd.DataFrame(rows)

    def test_first_run_baselines_without_sending_stock(self):
        sent = []
        with patch.object(watch, "STATE_DIR", self.state_dir),              patch.object(watch, "current_watch", return_value=self._df([101, 102])),              patch.object(watch, "recipient_names", return_value=["MikeChong"]),              patch.object(watch, "send_with_retry", side_effect=lambda *args: sent.append(args)),              patch.object(watch.base, "API_KEY", "test-key"):
            watch.main()

        self.assertEqual(sent, [])
        state = watch.load_state(self.state_dir / "mail_multi_grade_watch_current_MikeChong.csv")
        self.assertEqual(state, {101, 102})

    def test_existing_stock_is_suppressed_and_new_entry_is_sent(self):
        path = self.state_dir / "mail_multi_grade_watch_current_MikeChong.csv"
        watch.save_state(path, {101, 102})
        sent = []

        current = self._df([101, 102, 103])
        with patch.object(watch, "STATE_DIR", self.state_dir),              patch.object(watch, "current_watch", return_value=current),              patch.object(watch, "recipient_names", return_value=["MikeChong"]),              patch.object(watch, "live_rows", side_effect=lambda df: df.copy()),              patch.object(watch, "resolve_character", return_value=2124493042),              patch.object(watch, "send_with_retry", side_effect=lambda *args: sent.append(args)),              patch.object(watch.base, "API_KEY", "test-key"):
            watch.main()

        self.assertEqual(len(sent), 1)
        self.assertIn("1个", sent[0][1])
        state = watch.load_state(path)
        self.assertEqual(state, {101, 102, 103})

    def test_drop_then_reenter_counts_as_new(self):
        path = self.state_dir / "mail_multi_grade_watch_current_MikeChong.csv"
        watch.save_state(path, {101, 102})

        # 102 drops below A/S, so current state should forget it.
        with patch.object(watch, "STATE_DIR", self.state_dir),              patch.object(watch, "current_watch", return_value=self._df([101])),              patch.object(watch, "recipient_names", return_value=["MikeChong"]),              patch.object(watch.base, "API_KEY", "test-key"):
            watch.main()
        self.assertEqual(watch.load_state(path), {101})

        sent = []
        with patch.object(watch, "STATE_DIR", self.state_dir),              patch.object(watch, "current_watch", return_value=self._df([101, 102])),              patch.object(watch, "recipient_names", return_value=["MikeChong"]),              patch.object(watch, "live_rows", side_effect=lambda df: df.copy()),              patch.object(watch, "resolve_character", return_value=2124493042),              patch.object(watch, "send_with_retry", side_effect=lambda *args: sent.append(args)),              patch.object(watch.base, "API_KEY", "test-key"):
            watch.main()

        self.assertEqual(len(sent), 1)
        self.assertEqual(watch.load_state(path), {101, 102})


if __name__ == "__main__":
    unittest.main()
