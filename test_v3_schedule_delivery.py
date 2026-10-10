import unittest
from pathlib import Path

import pandas as pd

from bpc_light_probe import select_light_bpc_contracts
from send_v3_gmail_alerts import _eve_to_plain


class V3ScheduleAndDeliveryTests(unittest.TestCase):
    def test_light_bpc_probe_only_discovers_bpc_only_npc_station_contracts(self):
        now = pd.Timestamp("2026-10-07T10:00:00Z")
        contracts = pd.DataFrame([
            {
                "contract_id": 1,
                "type": "item_exchange",
                "price": 100_000_000,
                "date_expired": "2026-10-07T15:00:00Z",
                "start_location_id": 60003760,
            },
            {
                "contract_id": 2,
                "type": "item_exchange",
                "price": 6_000_000_000,
                "date_expired": "2026-10-07T15:00:00Z",
                "start_location_id": 60003760,
            },
            {
                "contract_id": 3,
                "type": "item_exchange",
                "price": 100_000_000,
                "date_expired": "2026-10-07T15:00:00Z",
                "start_location_id": 1_050_000_000_000,
            },
            {
                "contract_id": 4,
                "type": "item_exchange",
                "price": 100_000_000,
                "date_expired": "2026-10-07T15:00:00Z",
                "start_location_id": 60003760,
            },
            {
                "contract_id": 5,
                "type": "item_exchange",
                "price": 100_000_000,
                "date_expired": "2026-10-07T15:00:00Z",
                "start_location_id": 60003760,
            },
            {
                "contract_id": 6,
                "type": "item_exchange",
                "price": 100_000_000,
                "date_expired": "2026-10-07T11:00:00Z",
                "start_location_id": 60003760,
            },
        ])
        items = pd.DataFrame([
            {"contract_id": 1, "is_included": True, "is_blueprint_copy": True, "type_id": 1001, "runs": 10, "quantity": 1, "material_efficiency": 10, "time_efficiency": 20},
            {"contract_id": 2, "is_included": True, "is_blueprint_copy": True, "type_id": 1002, "runs": 10, "quantity": 1, "material_efficiency": 10, "time_efficiency": 20},
            {"contract_id": 3, "is_included": True, "is_blueprint_copy": True, "type_id": 1003, "runs": 10, "quantity": 1, "material_efficiency": 10, "time_efficiency": 20},
            {"contract_id": 4, "is_included": True, "is_blueprint_copy": True, "type_id": 1004, "runs": 10, "quantity": 1, "material_efficiency": 10, "time_efficiency": 20},
            {"contract_id": 4, "is_included": True, "is_blueprint_copy": False, "type_id": 2004, "runs": 0, "quantity": 1, "material_efficiency": 0, "time_efficiency": 0},
            {"contract_id": 5, "is_included": True, "is_blueprint_copy": True, "type_id": 1005, "runs": 10, "quantity": 1, "material_efficiency": 10, "time_efficiency": 20},
            {"contract_id": 5, "is_included": False, "is_blueprint_copy": False, "type_id": 3005, "runs": 0, "quantity": 1, "material_efficiency": 0, "time_efficiency": 0},
            {"contract_id": 6, "is_included": True, "is_blueprint_copy": True, "type_id": 1006, "runs": 10, "quantity": 1, "material_efficiency": 10, "time_efficiency": 20},
        ])
        got = select_light_bpc_contracts(
            contracts,
            items,
            now=now,
            max_contract_price=5_000_000_000,
            min_hours_to_expire=2,
        )
        self.assertEqual(got["contract_id"].tolist(), [1])
        self.assertEqual(int(got.iloc[0]["total_bpc_runs"]), 10)

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

    def test_cloudflare_fast_dedupe_and_three_hour_bpc_schedule(self):
        wrangler = Path("cloudflare/wrangler.jsonc").read_text(encoding="utf-8")
        worker = Path("cloudflare/worker_mail_sender.js").read_text(encoding="utf-8")
        self.assertIn('"*/15 * * * *"', wrangler)
        self.assertIn('"0 */3 * * *"', wrangler)
        self.assertIn('workflow = "scan.yml"', worker)
        self.assertIn('bpc_deep: { enabled: true', worker)
        self.assertIn('workflow = "v3-bpc-deep.yml"', worker)
        self.assertIn("workflowIsActive(env, workflow)", worker)
        self.assertIn("EVE_DISPATCH_TOKEN", worker)

    def test_fast_lane_has_no_heavy_bpc_work(self):
        fast = Path(".github/workflows/scan.yml").read_text(encoding="utf-8")
        deep = Path(".github/workflows/v3-bpc-deep.yml").read_text(encoding="utf-8")
        self.assertNotIn("python bpc_light_probe.py", fast)
        self.assertNotIn("v3-bpc-deep.yml --repo", fast)
        self.assertNotIn("python runner_buy_only.py", fast)
        self.assertIn("python runner_buy_only.py", deep)

    def test_gmail_delivery_replaces_calendar_delivery(self):
        fast = Path(".github/workflows/scan.yml").read_text(encoding="utf-8")
        deep = Path(".github/workflows/v3-bpc-deep.yml").read_text(encoding="utf-8")
        self.assertIn("send_v3_gmail_alerts.py", fast)
        self.assertIn("send_v3_gmail_alerts.py", deep)
        self.assertNotIn("send_v3_calendar_alerts.py", fast)
        self.assertNotIn("send_v3_calendar_alerts.py", deep)


if __name__ == "__main__":
    unittest.main()
