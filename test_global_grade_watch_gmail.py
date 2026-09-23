from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import send_global_grade_watch_gmail as gmail_watch


class GmailGradeWatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "gmail_seen.csv"

    def _record(self, key, cid, score=75.0):
        return {
            "opportunity_key": key,
            "contract_id": cid,
            "type_id": None,
            "score": score,
            "grade": "A",
            "status": "SAFE",
            "source_labels": ["普通合同V2"],
            "primary_source": "普通合同V2",
            "title": f"Opportunity {cid}",
            "profit": 35_000_000.0,
            "roi": 0.15,
            "stress_profit": 30_000_000.0,
            "system_name": "Jita",
            "station_name": "Jita IV - Moon 4",
            "risk_tier": "A1",
            "items": "",
            "note": "",
            "eve_contract_url": "",
            "eve_market_url": "",
        }

    def test_first_configured_run_baselines_without_sending(self):
        current = {"contract:101": self._record("contract:101", 101)}
        sent = []
        with patch.object(gmail_watch, "STATE", self.state),              patch.object(gmail_watch, "SMTP_USER", "me@gmail.com"),              patch.object(gmail_watch, "APP_PASSWORD", "app-pass"),              patch.object(gmail_watch, "RECIPIENT", "me@gmail.com"),              patch.object(gmail_watch.watch, "collect_candidates", return_value=(current, 10)),              patch.object(gmail_watch, "send_gmail", side_effect=lambda *args: sent.append(args)):
            gmail_watch.main()

        self.assertEqual(sent, [])
        self.assertEqual(gmail_watch.load_seen(), {"contract:101"})

    def test_new_first_seen_candidate_sends_once(self):
        with patch.object(gmail_watch, "STATE", self.state):
            gmail_watch.save_seen({"contract:101"})

        current = {
            "contract:101": self._record("contract:101", 101),
            "contract:102": self._record("contract:102", 102, 88.0),
        }
        sent = []
        with patch.object(gmail_watch, "STATE", self.state),              patch.object(gmail_watch, "SMTP_USER", "me@gmail.com"),              patch.object(gmail_watch, "APP_PASSWORD", "app-pass"),              patch.object(gmail_watch, "RECIPIENT", "me@gmail.com"),              patch.object(gmail_watch.watch, "collect_candidates", return_value=(current, 10)),              patch.object(gmail_watch.watch, "live_filter", side_effect=lambda rows: rows),              patch.object(gmail_watch, "send_gmail", side_effect=lambda *args: sent.append(args)):
            gmail_watch.main()
            gmail_watch.main()

        self.assertEqual(len(sent), 1)
        self.assertEqual(gmail_watch.load_seen(), {"contract:101", "contract:102"})

    def test_failed_delivery_does_not_mark_new_candidate_seen(self):
        with patch.object(gmail_watch, "STATE", self.state):
            gmail_watch.save_seen({"contract:101"})

        current = {
            "contract:101": self._record("contract:101", 101),
            "contract:103": self._record("contract:103", 103, 86.0),
        }
        with patch.object(gmail_watch, "STATE", self.state),              patch.object(gmail_watch, "SMTP_USER", "me@gmail.com"),              patch.object(gmail_watch, "APP_PASSWORD", "app-pass"),              patch.object(gmail_watch, "RECIPIENT", "me@gmail.com"),              patch.object(gmail_watch.watch, "collect_candidates", return_value=(current, 10)),              patch.object(gmail_watch.watch, "live_filter", side_effect=lambda rows: rows),              patch.object(gmail_watch, "send_gmail", side_effect=RuntimeError("smtp down")):
            with self.assertRaises(RuntimeError):
                gmail_watch.main()

        self.assertEqual(gmail_watch.load_seen(), {"contract:101"})


if __name__ == "__main__":
    unittest.main()
