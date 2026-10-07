import unittest
from pathlib import Path

import pandas as pd

from bpc_fast_probe import select_candidates
from send_v3_gmail_alerts import _eve_to_plain


class V3ScheduleAndDeliveryTests(unittest.TestCase):
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

    def test_gmail_plain_text_keeps_eve_mail_content(self):
        body = "<b>BPC制造｜1个</b><br>净利 <b>60.0M</b><br><url=contract:0//123><b>打开合同</b></url>"
        plain = _eve_to_plain(body)
        self.assertIn("BPC制造｜1个", plain)
        self.assertIn("净利 60.0M", plain)
        self.assertIn("打开合同", plain)
        self.assertNotIn("<b>", plain)
        self.assertNotIn("<url=", plain)

    def test_github_workflows_are_dispatch_only(self):
        fast = Path(".github/workflows/scan.yml").read_text(encoding="utf-8")
        deep = Path(".github/workflows/v3-bpc-deep.yml").read_text(encoding="utf-8")
        fast_on = fast.split("permissions:", 1)[0]
        deep_on = deep.split("permissions:", 1)[0]
        self.assertIn("workflow_dispatch", fast_on)
        self.assertNotIn("schedule:", fast_on)
        self.assertIn("workflow_dispatch", deep_on)
        self.assertNotIn("schedule:", deep_on)

    def test_cloudflare_owns_15m_and_3h_crons(self):
        wrangler = Path("cloudflare/wrangler.jsonc").read_text(encoding="utf-8")
        worker = Path("cloudflare/worker_mail_sender.js").read_text(encoding="utf-8")
        self.assertIn('"*/15 * * * *"', wrangler)
        self.assertIn('"0 */3 * * *"', wrangler)
        self.assertIn('workflow = "scan.yml"', worker)
        self.assertIn('workflow = "v3-bpc-deep.yml"', worker)
        self.assertIn("GITHUB_DISPATCH_TOKEN", worker)

    def test_gmail_delivery_replaces_calendar_delivery(self):
        fast = Path(".github/workflows/scan.yml").read_text(encoding="utf-8")
        deep = Path(".github/workflows/v3-bpc-deep.yml").read_text(encoding="utf-8")
        self.assertIn("send_v3_gmail_alerts.py", fast)
        self.assertIn("send_v3_gmail_alerts.py", deep)
        self.assertNotIn("send_v3_calendar_alerts.py", fast)
        self.assertNotIn("send_v3_calendar_alerts.py", deep)


if __name__ == "__main__":
    unittest.main()
