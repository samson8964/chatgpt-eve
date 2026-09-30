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
            "profit": 120_000_000.0,
            "roi": 0.20,
            "stress_profit": 105_000_000.0,
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
                "instant_net_profit": 131_000_000,
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
                "net_profit": 135_000_000,
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
                "net_profit": 150_000_000,
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
                "net_profit": 140_000_000,
                "net_roi": 0.13,
            }
        ]).to_csv(self.latest / "v3_jita_to_four_h.csv", index=False)

        with patch.object(watch, "LATEST", self.latest):
            candidates, _ = watch.collect_candidates()

        self.assertIn("market:4h-to-jita:34", candidates)
        self.assertIn("market:jita-to-4h:34", candidates)

    def test_bpc_value_signal_is_watch_only_never_auto_mailed(self):
        pd.DataFrame([
            {
                "contract_id": 7001,
                "v2_value_score": 99.0,
                "v2_value_status": "VALUE_SIGNAL",
                "chosen_value_gap": -50_000_000,
                "chosen_roi": -1.0,
                "blueprint_name": "Council Diplomatic Shuttle Blueprint",
            }
        ]).to_csv(self.latest / "bpc_value_opportunities_v2.csv", index=False)

        with patch.object(watch, "LATEST", self.latest):
            candidates, readable = watch.collect_candidates()

        self.assertEqual(readable, 1)
        self.assertEqual(candidates, {})

    def test_bpc_manufacturing_must_pass_strict_profit_gate(self):
        pd.DataFrame([
            {
                "contract_id": 8001,
                "v2_score": 95.0,
                "v2_grade": "S",
                "v2_status": "SAFE",
                "v2_live_net_profit": 5_000_000,
                "v2_live_net_roi": 0.03,
                "v2_stress_net_profit": 1_000_000,
                "v2_orderbook_complete": True,
                "blueprint_name": "Bad BPC",
            },
            {
                "contract_id": 8002,
                "v2_score": 88.0,
                "v2_grade": "S",
                "v2_status": "SAFE",
                "v2_live_net_profit": 140_000_000,
                "v2_live_net_roi": 0.20,
                "v2_stress_net_profit": 25_000_000,
                "v2_orderbook_complete": True,
                "blueprint_name": "Good BPC",
            },
        ]).to_csv(self.latest / "ranked_opportunities_v2.csv", index=False)

        with patch.object(watch, "LATEST", self.latest):
            candidates, _ = watch.collect_candidates()

        self.assertNotIn("contract:8001", candidates)
        self.assertIn("contract:8002", candidates)

    def test_high_score_below_50m_is_never_auto_mailed(self):
        pd.DataFrame([
            {
                "contract_id": 8999,
                "opportunity_score": 99.0,
                "score_grade": "S",
                "execution_status": "SAFE",
                "net_profit": 49_999_999,
                "net_roi": 0.50,
                "contract_title": "Below hard mail floor",
            }
        ]).to_csv(self.latest / "contract_deals_all.csv", index=False)

        with patch.object(watch, "LATEST", self.latest):
            candidates, _ = watch.collect_candidates()

        self.assertNotIn("contract:8999", candidates)

    def test_high_score_negative_profit_is_never_auto_mailed(self):
        pd.DataFrame([
            {
                "contract_id": 9001,
                "opportunity_score": 99.0,
                "score_grade": "S",
                "execution_status": "SAFE",
                "net_profit": -1_000_000,
                "net_roi": -0.01,
                "contract_title": "High score but losing money",
            }
        ]).to_csv(self.latest / "contract_deals_all.csv", index=False)

        with patch.object(watch, "LATEST", self.latest):
            candidates, _ = watch.collect_candidates()

        self.assertNotIn("contract:9001", candidates)

    def test_v2_live_values_override_stale_snapshot_values(self):
        row = pd.Series({
            "net_profit": 100_000_000,
            "net_roi": 0.50,
            "stress_net_profit": 90_000_000,
            "v2_live_net_profit": 25_000_000,
            "v2_live_net_roi": 0.12,
            "v2_stress_net_profit": 20_000_000,
        })
        self.assertEqual(watch.candidate_profit(row), 25_000_000)
        self.assertAlmostEqual(watch.candidate_roi(row), 0.12)
        self.assertEqual(watch.candidate_stress(row), 20_000_000)


if __name__ == "__main__":
    unittest.main()
