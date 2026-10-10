import unittest
from datetime import datetime, timedelta, timezone

import pandas as pd

from v3_bpc_adapter import classify_manufacturing_row, intrinsic_rows, manufacturing_rows
from send_v3_opportunity_mail import CHANNELS, render


def strict_row(**overrides):
    row = {
        "contract_id": 123,
        "v2_status": "SAFE",
        "v2_grade": "A",
        "v2_score": 80,
        "v2_live_net_profit": 100_000_000,
        "v2_live_net_roi": 0.15,
        "v2_stress_net_profit": 50_000_000,
        "v2_verified_at": datetime.now(timezone.utc).isoformat(),
        "v2_jita_manufacturing_cost_complete": True,
        "v2_jita_manufacturing_job_cost": 10_000_000,
        "v2_jita_live_net_profit": 50_000_000,
        "v2_jita_live_net_roi": 0.10,
        "v2_jita_stress_net_profit": 1,
        "v2_orderbook_complete": True,
        "blueprints": "1x Test Blueprint",
        "products": "10x Test Product",
        "contract_price": 20_000_000,
    }
    row.update(overrides)
    return row


class V3BpcAdapterTests(unittest.TestCase):
    def test_approved_seven_gate_boundary_becomes_mail(self):
        stage, eligible, reason = classify_manufacturing_row(strict_row())
        self.assertEqual(stage, "MAIL")
        self.assertTrue(eligible)
        self.assertEqual(reason, "BPC_APPROVED_SEVEN_GATE_PASSED")

    def test_legacy_remote_failure_blocks_mail(self):
        stage, eligible, _ = classify_manufacturing_row(
            strict_row(
                v2_status="CHANGED",
                v2_live_net_profit=-500_000_000,
                v2_live_net_roi=-1.0,
                v2_stress_net_profit=-500_000_000,
            )
        )
        self.assertEqual(stage, "WATCH")
        self.assertFalse(eligible)

    def test_stale_verification_and_remote_profit_fail_closed(self):
        stage, eligible, reason = classify_manufacturing_row(
            strict_row(v2_verified_at=(datetime.now(timezone.utc) - timedelta(hours=48)).isoformat())
        )
        self.assertEqual((stage, eligible, reason), ("RESEARCH", False, "BPC_LIVE_VERIFICATION_STALE_OR_MISSING"))
        stage, eligible, reason = classify_manufacturing_row(
            strict_row(v2_live_net_profit=99_999_999)
        )
        self.assertEqual((stage, eligible, reason), ("WATCH", False, "BPC_REMOTE_RISK_GATE_FAILED"))

    def test_jita_profit_below_50m_is_watch(self):
        stage, eligible, reason = classify_manufacturing_row(
            strict_row(v2_jita_live_net_profit=49_999_999)
        )
        self.assertEqual(stage, "WATCH")
        self.assertFalse(eligible)
        self.assertEqual(reason, "BPC_JITA_PROFIT_BELOW_50M")

    def test_jita_roi_below_10pct_is_watch(self):
        stage, eligible, reason = classify_manufacturing_row(
            strict_row(v2_jita_live_net_roi=0.0999)
        )
        self.assertEqual(stage, "WATCH")
        self.assertFalse(eligible)
        self.assertEqual(reason, "BPC_JITA_ROI_BELOW_10PCT")

    def test_stress_must_be_positive(self):
        stage, eligible, reason = classify_manufacturing_row(
            strict_row(v2_jita_stress_net_profit=0)
        )
        self.assertEqual(stage, "WATCH")
        self.assertFalse(eligible)
        self.assertEqual(reason, "BPC_JITA_STRESS_NOT_POSITIVE")

    def test_material_and_product_depth_must_be_complete(self):
        stage, eligible, reason = classify_manufacturing_row(
            strict_row(v2_orderbook_complete=False)
        )
        self.assertEqual(stage, "RESEARCH")
        self.assertFalse(eligible)
        self.assertEqual(reason, "BPC_JITA_COST_OR_ORDERBOOK_INCOMPLETE")

    def test_adapter_uses_jita_manufacturing_economics(self):
        rows = manufacturing_rows(pd.DataFrame([strict_row()]))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["net_profit"], 50_000_000)
        self.assertAlmostEqual(rows[0]["net_roi"], 0.10)
        self.assertEqual(rows[0]["stress_net_profit"], 1)
        self.assertTrue(rows[0]["mail_eligible"])

    def test_intrinsic_signal_stays_watch_only(self):
        df = pd.DataFrame([{
            "contract_id": 456,
            "v2_value_status": "VALUE_SIGNAL",
            "v2_value_score": 90,
            "v2_value_confidence": 0.8,
            "bpc_intrinsic_value_surplus": 500_000_000,
            "blueprints": "10x Rare Blueprint",
        }])
        rows = intrinsic_rows(df, set())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["policy_stage"], "WATCH")
        self.assertFalse(rows[0]["mail_eligible"])

    def test_bpc_mail_layout_is_compact(self):
        row = pd.Series({
            "products": "10x Test Product",
            "blueprints": "1x Test Blueprint",
            "contract_price": 20_000_000,
            "stress_net_profit": 15_000_000,
        })
        picked = [{
            "id": 123,
            "profit": 60_000_000,
            "roi": 0.12,
            "score": 80,
            "grade": "A",
            "row": row,
        }]
        subject, body = render("v3-bpc", "10-07 15:00", picked)
        self.assertEqual(subject, "[V3] BPC制造 · 1个 · 10-07 15:00")
        self.assertIn("Jita制造净利", body)
        self.assertIn("ROI 12.0%", body)
        self.assertNotIn("成品VWAP", body)
        self.assertNotIn("材料最大滑点", body)
        self.assertNotIn("Opportunity Engine V3", body)

    def test_unified_mailer_has_all_production_source_types(self):
        for key in [
            "v3-bpc",
            "v3-four-h-contract",
            "v3-cj-contract",
            "v3-amarr-to-jita",
            "v3-dodixie-to-jita",
            "v3-four-h-to-jita",
            "v3-cj-to-jita",
            "v3-jita-to-4h",
        ]:
            self.assertIn(key, CHANNELS)


if __name__ == "__main__":
    unittest.main()
