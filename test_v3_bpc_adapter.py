import unittest

import pandas as pd

from v3_bpc_adapter import classify_manufacturing_row, intrinsic_rows, manufacturing_rows
from send_v3_opportunity_mail import CHANNELS


def strict_row(**overrides):
    row = {
        "contract_id": 123,
        "v2_status": "SAFE",
        "v2_grade": "A",
        "v2_score": 80,
        "v2_live_net_profit": 120_000_000,
        "v2_live_net_roi": 0.20,
        "v2_stress_net_profit": 60_000_000,
        "v2_jita_manufacturing_cost_complete": True,
        "v2_jita_manufacturing_job_cost": 10_000_000,
        "v2_jita_live_net_profit": 80_000_000,
        "v2_jita_live_net_roi": 0.12,
        "v2_jita_stress_net_profit": 30_000_000,
        "v2_orderbook_complete": True,
        "blueprints": "1x Test Blueprint",
        "products": "10x Test Product",
    }
    row.update(overrides)
    return row


class V3BpcAdapterTests(unittest.TestCase):
    def test_strict_bpc_becomes_mail(self):
        stage, eligible, reason = classify_manufacturing_row(strict_row())
        self.assertEqual(stage, "MAIL")
        self.assertTrue(eligible)
        self.assertEqual(reason, "BPC_STRICT_JITA_MANUFACTURING_GATE_PASSED")

    def test_safe_but_below_strict_gate_is_watch(self):
        stage, eligible, _ = classify_manufacturing_row(
            strict_row(v2_live_net_profit=90_000_000)
        )
        self.assertEqual(stage, "WATCH")
        self.assertFalse(eligible)

    def test_changed_bpc_never_mails(self):
        stage, eligible, _ = classify_manufacturing_row(
            strict_row(v2_status="CHANGED")
        )
        self.assertEqual(stage, "WATCH")
        self.assertFalse(eligible)

    def test_adapter_uses_conservative_jita_profit_for_mail(self):
        rows = manufacturing_rows(pd.DataFrame([strict_row()]))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["net_profit"], 80_000_000)
        self.assertAlmostEqual(rows[0]["net_roi"], 0.12)
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
