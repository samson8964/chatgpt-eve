"""Pure read-only diagnostic regression tests; no ESI or live inputs."""
import json
import tempfile
import unittest
from pathlib import Path

from v4.station_funnel_audit import gates, run_one

FOUR_H = 1053970513596
CJ = 1049588174021
O4T = 1040804972352

class StationFunnelAuditTests(unittest.TestCase):
    def test_distinguishes_each_gate_and_strict_50m_boundary(self):
        proof = {"reason": "BELOW_GATE_OR_STRESS", "profit": 60_000_000,
                 "roi": 0.09, "density": 1700,
                 "stress_profit": 50_000_000}
        self.assertEqual(gates(proof), ["ROI_BELOW_10_PERCENT",
                         "DENSITY_BELOW_2000_PER_M3",
                         "JITA_BUY_STRESS_NET_NOT_ABOVE_50M"])
        proof.update(roi=.11, density=2000, stress_profit=50_000_001)
        self.assertEqual(gates(proof), ["REASON_CONFLICT_WITH_NUMERIC_GATES"])
        self.assertEqual(gates({"reason":"NO_PROFITABLE_MATCHED_DEPTH"}),
                         ["NO_PROFITABLE_MATCHED_DEPTH"])
        self.assertEqual(gates({"model_candidate":True}), ["MODEL_PASS_SNAPSHOT_NOT_LIVE"])

    def test_run_one_preserves_station_source_proofs_and_near_misses(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            (folder/"deep_shadow.json").write_text(json.dumps({
                "market_execution_basis": "OPTIMIZED_MATCHED_QUANTITY_AND_VWAP",
                "market_station_sell_census": {
                    "4-H":{"active_sell_type_ids":5000,"sell_types_optimistic_gate_passed":1},
                    "O4T":{"active_sell_type_ids":2200,"sell_types_optimistic_gate_passed":1}}}),
                encoding="utf-8")
            rows = [
                {"kind":"market","source_location":FOUR_H, "type_id":13,
                 "reason":"BELOW_GATE_OR_STRESS", "profit":90_000_000,
                 "roi":.15,"density":5000, "stress_profit":30_000_000},
                {"kind":"market","source_location":O4T,"type_id":14,
                 "reason":"NO_PROFITABLE_MATCHED_DEPTH"},
                {"kind":"market","source_location":CJ,"type_id":15,
                 "model_candidate":True,"reason":"LIVE_ORDER_AND_CONTRACT_NOT_REVALIDATED",
                 "profit": 80_000_000, "stress_profit":60_000_000},
                {"kind":"contract","source_location":FOUR_H,"reason":"BELOW_GATE_OR_STRESS"}]
            (folder/"all_proofs.jsonl").write_text(
                "".join(json.dumps(row)+"\n" for row in rows),encoding="utf-8")
            result=run_one(folder)
            self.assertEqual(result["stations"]["4-H"]["deep_proofs"],1)
            self.assertEqual(result["stations"]["4-H"]["normal_gates_pass_but_stress_fails"],1)
            self.assertEqual(result["stations"]["O4T"]["rejection_reasons"],
                             {"NO_PROFITABLE_MATCHED_DEPTH":1})
            self.assertEqual(len(result["stations"]["C-J"]["model_candidates"]),1)
            self.assertEqual(result["stations"]["4-H"]["census"]["active_sell_type_ids"],5000)

if __name__=="__main__":
    unittest.main()
