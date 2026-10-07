import unittest
from pathlib import Path

import pandas as pd

from bpc_fast_probe import select_candidates
from send_v3_calendar_alerts import _event_id, _plain


class V3ScheduleAndCalendarTests(unittest.TestCase):
    def test_bpc_fast_probe_uses_snapshot_jita_50m_10pct_gate(self):
        df = pd.DataFrame([
            {
                "contract_id": 1,
                "jita_manufacturing_cost_complete": True,
                "jita_manufacturing_net_profit": 50_000_000,
                "jita_manufacturing_net_roi": 0.10,
            },
            {
                "contract_id": 2,
                "jita_manufacturing_cost_complete": True,
                "jita_manufacturing_net_profit": 49_999_999,
                "jita_manufacturing_net_roi": 0.50,
            },
            {
                "contract_id": 3,
                "jita_manufacturing_cost_complete": True,
                "jita_manufacturing_net_profit": 500_000_000,
                "jita_manufacturing_net_roi": 0.0999,
            },
            {
                "contract_id": 4,
                "jita_manufacturing_cost_complete": False,
                "jita_manufacturing_net_profit": 500_000_000,
                "jita_manufacturing_net_roi": 0.50,
            },
        ])
        got = select_candidates(df)
        self.assertEqual(got["contract_id"].tolist(), [1])

    def test_calendar_plain_text_keeps_mail_content_without_eve_markup(self):
        body = "<b>BPC制造｜1个</b><br>净利 <b>60.0M</b><br><url=contract:0//123><b>打开合同</b></url>"
        plain = _plain(body)
        self.assertIn("BPC制造｜1个", plain)
        self.assertIn("净利 60.0M", plain)
        self.assertIn("打开合同", plain)
        self.assertNotIn("<b>", plain)
        self.assertNotIn("<url=", plain)

    def test_calendar_event_id_is_stable_per_channel_and_opportunity(self):
        self.assertEqual(_event_id("v3-bpc", 123), _event_id("v3-bpc", 123))
        self.assertNotEqual(_event_id("v3-bpc", 123), _event_id("v3-bpc", 124))
        self.assertNotEqual(_event_id("v3-bpc", 123), _event_id("v3-four-h-contract", 123))

    def test_workflow_cadence_is_split(self):
        fast = Path(".github/workflows/scan.yml").read_text(encoding="utf-8")
        deep = Path(".github/workflows/v3-bpc-deep.yml").read_text(encoding="utf-8")
        self.assertIn("cron: '*/15 * * * *'", fast)
        self.assertIn("Lightweight BPC discovery probe", fast)
        self.assertNotIn("Run BPC specialist live revalidation", fast)
        self.assertIn("cron: '0 */3 * * *'", deep)
        self.assertIn("Run BPC specialist live revalidation", deep)
        self.assertIn("V3_CHANNELS: 'v3-bpc'", deep)

    def test_fast_workflow_has_no_workflow_dispatch_to_avoid_legacy_scheduler_duplicates(self):
        fast = Path(".github/workflows/scan.yml").read_text(encoding="utf-8")
        on_block = fast.split("permissions:", 1)[0]
        self.assertNotIn("workflow_dispatch", on_block)


if __name__ == "__main__":
    unittest.main()
