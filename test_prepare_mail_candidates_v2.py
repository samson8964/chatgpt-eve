import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import prepare_mail_candidates as gate


class PrepareMailCandidatesV2Tests(unittest.TestCase):
    def test_v2_gate_only_keeps_safe_manufacturing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base_path = root / "ranked.csv"
            v2_path = root / "ranked_v2.csv"
            value_path = root / "value.csv"

            pd.DataFrame([
                {"contract_id": 1, "net_profit": 1, "net_roi": 0.01, "opportunity_score": 1},
                {"contract_id": 2, "net_profit": 999000000, "net_roi": 0.99, "opportunity_score": 99},
                {"contract_id": 3, "net_profit": 999000000, "net_roi": 0.99, "opportunity_score": 99},
            ]).to_csv(base_path, index=False)

            pd.DataFrame([
                {"contract_id": 1, "v2_status": "SAFE", "v2_grade": "A", "v2_score": 82, "v2_live_net_profit": 55000000, "v2_live_net_roi": 0.18, "v2_stress_net_profit": 20000000, "v2_orderbook_complete": True},
                {"contract_id": 2, "v2_status": "CHANGED", "v2_grade": "C", "v2_score": 40, "v2_live_net_profit": 200000000, "v2_live_net_roi": 0.30, "v2_stress_net_profit": -1, "v2_orderbook_complete": True},
                {"contract_id": 3, "v2_status": "SAFE", "v2_grade": "B", "v2_score": 65, "v2_live_net_profit": 15000000, "v2_live_net_roi": 0.20, "v2_stress_net_profit": 10000000, "v2_orderbook_complete": True},
            ]).to_csv(v2_path, index=False)

            pd.DataFrame([{"contract_id": 99, "bpc_intrinsic_value_surplus": 500000000}]).to_csv(value_path, index=False)

            with patch.object(gate, "BPC", base_path), patch.object(gate, "BPC_V2", v2_path), patch.object(gate, "BPC_VALUE", value_path):
                got = gate.prepare_bpc_v2_gate()

            self.assertEqual(list(got.loc[got["mail_eligible"], "contract_id"]), [1])
            row = got.loc[got["contract_id"].eq(1)].iloc[0]
            self.assertEqual(row["net_profit"], 55000000)
            self.assertAlmostEqual(row["net_roi"], 0.18)
            self.assertEqual(row["mail_filter_reason"], "V2_SAFE_MANUFACTURING")

            value = pd.read_csv(value_path)
            self.assertFalse(value["mail_eligible"].any())
            self.assertEqual(value.iloc[0]["mail_filter_reason"], "V2_VALUE_SIGNAL_WATCH_ONLY")


if __name__ == "__main__":
    unittest.main()
