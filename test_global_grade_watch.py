from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import send_global_grade_watch as watch


class GlobalGradeWatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / "state"
        self.latest = self.root / "latest"
        self.latest.mkdir(parents=True, exist_ok=True)

    def _record(self, key, cid, score=75.0, source="普通合同V2"):
        return {
            "opportunity_key": key,
            "contract_id": cid,
            "type_id": None,
            "score": score,
            "grade": "A" if score < 85 else "S",
            "status": "SAFE",
            "source_labels": [source],
            "primary_source": source,
            "title": f"Opportunity {cid}",
            "profit": 20_000_000.0,
            "roi": 0.20,
            "stress_profit": 15_000_000.0,
            "system_name": "Jita",
            "station_name": "Jita IV - Moon 4",
            "risk_tier": "A1",
            "items": "",
            "note": "",
            "eve_contract_url": "",
            "eve_market_url": "",
        }

    def test_first_run_baselines_stock_without_mail(self):
        current = {"contract:101": self._record("contract:101", 101)}
        sent = []
        with patch.object(watch, "STATE_DIR", self.state),              patch.object(watch, "collect_candidates", return_value=(current, 10)),              patch.object(watch, "recipient_names", return_value=["MikeChong"]),              patch.object(watch, "send_with_retry", side_effect=lambda *args: sent.append(args)),              patch.object(watch.base, "API_KEY", "test-key"):
            watch.main()

        self.assertEqual(sent, [])
        seen = watch.load_seen(self.state / "mail_global_grade_watch_seen_MikeChong.csv")
        self.assertEqual(seen, {"contract:101"})

    def test_only_first_seen_high_score_is_mailed_once(self):
        state_path = self.state / "mail_global_grade_watch_seen_MikeChong.csv"
        watch.save_seen(state_path, {"contract:101"})
        current = {
            "contract:101": self._record("contract:101", 101),
            "contract:102": self._record("contract:102", 102, score=88.0),
        }
        sent = []

        with patch.object(watch, "STATE_DIR", self.state),              patch.object(watch, "collect_candidates", return_value=(current, 10)),              patch.object(watch, "recipient_names", return_value=["MikeChong"]),              patch.object(watch, "live_filter", side_effect=lambda rows: rows),              patch.object(watch, "resolve_character", return_value=2124493042),              patch.object(watch, "send_with_retry", side_effect=lambda *args: sent.append(args)),              patch.object(watch.base, "API_KEY", "test-key"):
            watch.main()
            watch.main()

        self.assertEqual(len(sent), 1)
        seen = watch.load_seen(state_path)
        self.assertEqual(seen, {"contract:101", "contract:102"})

    def test_same_contract_across_engines_deduplicates_to_highest_score(self):
        pd.DataFrame([
            {
                "contract_id": 555,
                "opportunity_score": 72.0,
                "score_grade": "A",
                "execution_status": "SAFE",
                "instant_net_profit": 31_000_000,
                "instant_net_roi": 0.11,
                "contract_title": "same contract",
            }
        ]).to_csv(self.latest / "contract_deals_all.csv", index=False)
        pd.DataFrame([
            {
                "contract_id": 555,
                "opportunity_score": 81.0,
                "score_grade": "A",
                "execution_status": "SAFE",
                "net_profit": 35_000_000,
                "net_roi": 0.14,
                "contract_title": "same contract",
            }
        ]).to_csv(self.latest / "v3_cash_floor.csv", index=False)

        with patch.object(watch, "LATEST", self.latest):
            candidates, readable = watch.collect_candidates()

        self.assertEqual(readable, 2)
        self.assertEqual(set(candidates), {"contract:555"})
        row = candidates["contract:555"]
        self.assertEqual(row["score"], 81.0)
        self.assertEqual(set(row["source_labels"]), {"普通合同V2", "V3现金底价"})

    def test_market_directions_are_distinct_identities(self):
        pd.DataFrame([
            {
                "type_id": 34,
                "item_name": "Tritanium",
                "opportunity_score": 75.0,
                "score_grade": "A",
                "execution_status": "SAFE",
                "net_profit": 50_000_000,
                "net_roi": 0.15,
            }
        ]).to_csv(self.latest / "four_h_to_jita_buy.csv", index=False)
        pd.DataFrame([
            {
                "type_id": 34,
                "item_name": "Tritanium",
                "opportunity_score": 78.0,
                "score_grade": "A",
                "execution_status": "SAFE",
                "net_profit": 40_000_000,
                "net_roi": 0.13,
            }
        ]).to_csv(self.latest / "v3_jita_to_four_h.csv", index=False)

        with patch.object(watch, "LATEST", self.latest):
            candidates, _ = watch.collect_candidates()

        self.assertIn("market:4h-to-jita:34", candidates)
        self.assertIn("market:jita-to-4h:34", candidates)


if __name__ == "__main__":
    unittest.main()
