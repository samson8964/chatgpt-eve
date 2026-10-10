import tempfile
import math
import unittest
from pathlib import Path

from v3_engine import (
    ExecutionProof,
    PolicyConfig,
    RejectionFunnel,
    contract_fingerprint,
    evaluate_execution,
    evaluate_listing,
    load_fingerprints,
    save_fingerprints,
    is_full_cash_exit,
)


def proof(**overrides):
    data = dict(
        opportunity_id="1",
        channel="PARTIAL_CASH_FLOOR",
        source_cost=100_000_000,
        destination_value=170_000_000,
        sales_tax=0,
        haul_cost=5_000_000,
        volume_m3=1000,
        access_verified=True,
        stress_value=160_000_000,
        coverage=0.8,
        net_profit=65_000_000,
        net_roi=0.60,
        stress_net_profit=55_000_000,
        profit_per_m3=65_000,
        market_change_pct=0.02,
    )
    data.update(overrides)
    return ExecutionProof(**data)


class V3ArchitectureTests(unittest.TestCase):
    def test_formal_mail_gate_is_separate_from_safe_gate(self):
        cfg = PolicyConfig(full_cash_mail_enabled=True)
        self.assertEqual(evaluate_execution(proof(net_profit=40_000_000), cfg).stage, "SAFE")
        decision = evaluate_execution(proof(net_profit=60_000_000), cfg)
        self.assertEqual(decision.stage, "MAIL")
        self.assertTrue(decision.mail_eligible)

    def test_invalid_volume_and_infinite_profit_density_never_mail(self):
        cfg = PolicyConfig(full_cash_mail_enabled=True)
        for bad in (proof(volume_m3=0, profit_per_m3=math.inf),
                    proof(volume_m3=0, profit_per_m3=65000),
                    proof(volume_m3=1000, profit_per_m3=math.inf),
                    proof(volume_m3=float("nan"), profit_per_m3=65000)):
            decision = evaluate_execution(bad, cfg)
            self.assertFalse(decision.mail_eligible)
            self.assertEqual(decision.reason, "VOLUME_OR_DENSITY_UNVERIFIED")

    def test_full_cash_mail_is_disabled_during_parallel_rollout(self):
        cfg = PolicyConfig(full_cash_mail_enabled=False)
        decision = evaluate_execution(proof(channel="FULL_CASH", net_profit=80_000_000), cfg)
        self.assertEqual(decision.stage, "SAFE")
        self.assertFalse(decision.mail_eligible)

    def test_full_cash_depends_on_live_completeness_not_stress_book(self):
        self.assertTrue(is_full_cash_exit(coverage=1.0, filled_units=221294, requested_units=221294))
        self.assertFalse(is_full_cash_exit(coverage=0.99, filled_units=220000, requested_units=221294))

    def test_stress_failure_never_safe(self):
        decision = evaluate_execution(proof(stress_net_profit=-1), PolicyConfig())
        self.assertEqual(decision.stage, "WATCH")
        self.assertFalse(decision.mail_eligible)

    def test_listing_never_becomes_cash_safe(self):
        p = proof(channel="CONSERVATIVE_LIST", net_profit=100_000_000)
        decision = evaluate_listing(p, PolicyConfig(), max_fill_days=14, estimated_fill_days=3)
        self.assertEqual(decision.stage, "WATCH")
        self.assertEqual(decision.confidence_class, "LIST-SUPPORTED")
        self.assertFalse(decision.mail_eligible)

    def test_fingerprint_changes_when_contract_contents_change(self):
        a = contract_fingerprint(1, 10, {34: 5}, {}, 60003760, "2026-10-08")
        b = contract_fingerprint(1, 10, {34: 6}, {}, 60003760, "2026-10-08")
        self.assertNotEqual(a, b)

    def test_fingerprint_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            save_fingerprints(path, {1: "abc"})
            self.assertEqual(load_fingerprints(path), {1: "abc"})

    def test_funnel_records_stages_and_reasons(self):
        f = RejectionFunnel()
        f.stage("raw", 100)
        f.reject("LOW_PROFIT", 3)
        self.assertEqual(f.to_dict()["stages"]["raw"], 100)
        self.assertEqual(f.to_dict()["rejection_reasons"]["LOW_PROFIT"], 3)


if __name__ == "__main__":
    unittest.main()
