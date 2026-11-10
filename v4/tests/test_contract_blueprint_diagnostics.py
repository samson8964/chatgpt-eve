"""No-network contract and blueprint funnel diagnostic regression tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v4.contract_blueprint_diagnostics import inspect_run, latest_folders


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


class FunnelDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.runs = self.root / "runs"
        self.runs.mkdir()

    def make_run(self, name="20261110T092301Z-fake", finished=True,
                 proofs=None, recipes="INSTALLED"):
        folder = self.runs / name
        folder.mkdir()
        write_json(folder/"manifest.json", {
            "status":"SHADOW_RECORDED" if finished else "STARTED",
            "finished_at":"2026-11-10T09:27:11+00:00",
            "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
        })
        data = proofs or [
            {"kind":"contract","reason":"BELOW_GATE_OR_STRESS",
             "net_profit":-2,"roi":-.3,
             "ignored_no_bid_types":2,"ignored_blueprint_types":1},
            {"kind":"contract","reason":"LIVE_ORDER_AND_CONTRACT_NOT_REVALIDATED",
             "model_candidate":True,"net_profit":60_000_000,"roi":.24,
             "cargo_volume_m3":50060},
            {"kind":"blueprint_manufacturing",
             "reason":"BLUEPRINT_MANUFACTURING_MODEL_ESTIMATE_FEE_UNVERIFIED",
             "model_candidate":True, "net_profit":100_000_000,"roi":.55,
             "blueprint_type_id":86021},
            {"kind":"blueprint_manufacturing",
             "reason":"BLUEPRINT_MANUFACTURING_MODEL_ESTIMATE_FEE_UNVERIFIED",
             "model_candidate":False, "net_profit":10_000_000,"roi":.03,
             "blueprint_type_id":86021},
        ]
        write_json(folder/"deep_shadow.json",{
            "status":"SHADOW_ONLY_NO_LIVE_ALERTS",
            "contract_cash_known_location":1234,
            "contract_approved_locations_examined":333,
            "contract_requested_items_excluded":17,
            "contract_jita_examined":88,
            "npc_catalog_status":"INSTALLED_SDE_FULL_NPC_HIGH_LOW",
            "blueprint_manufacturing_recipe_status":recipes,
            "blueprint_manufacturing_recipe_count":24000 if recipes=="INSTALLED" else 0,
            "contract_blueprint_states":{"BPC":123,"BPO":5,"UNKNOWN_BLUEPRINT":17},
            "blueprint_manufacturing_valuation_errors":0,
            "proof_count":len(data),
            "structure_health":{"cj":{"status":"COMPLETE"}},
        })
        write_json(folder/"full_market_report.json", {
            "contracts":{"contract_rows_total":22000,
                         "contract_item_rows_total":198000}})
        with (folder/"all_proofs.jsonl").open("w", encoding="utf-8") as fh:
            for value in data: fh.write(json.dumps(value)+"\n")
        return folder

    def test_aggregate_reasons_and_proof_counts_are_truthful(self):
        folder = self.make_run()
        report = inspect_run(folder)
        self.assertEqual(report["status"], "READ_ONLY_FUNNEL_REPORTED")
        self.assertEqual(report["proofs"]["contract_model_candidates"], 1)
        self.assertEqual(report["proofs"]["contract_numeric_gate_but_below_2000_isk_per_m3_market_reference"], 1)
        self.assertEqual(report["proofs"]["contract_numeric_gate_before_mail_exclusions"], 1)
        self.assertEqual(report["proofs"]["blueprint_manufacturing_proofs_generated"], 2)
        self.assertEqual(report["proofs"]["blueprint_manufacturing_model_candidates"], 1)
        self.assertEqual(report["proofs"]["distinct_blueprint_type_ids_in_manufacturing_proofs"],1)
        self.assertEqual(report["blueprint_reference"]["ordinary_contract_blueprint_type_credits_ignored"],1)
        self.assertEqual(report["blueprint_reference"]["ordinary_contract_types_without_jita_buy_depth"],2)
        self.assertEqual(report["public_contract_ingestion"]["approved_cash_contracts"],333)
        self.assertFalse(report["local_files_modified"])
        self.assertFalse(report["mail_sent"])
        self.assertFalse(report["market_scan_started"])

    def test_missing_recipe_reports_zero_proofs_but_not_zero_blueprints(self):
        folder=self.make_run(proofs=[
            {"kind":"contract","reason":"NO_JITA_BUY_LIQUIDITY_FOR_REGULAR_SUBSET",
             "ignored_blueprint_types":5}
        ],recipes="NOT_INSTALLED")
        report=inspect_run(folder)
        self.assertEqual(report["proofs"]["blueprint_manufacturing_proofs_generated"],0)
        self.assertEqual(report["blueprint_reference"]["recipe_status_at_scan"],"NOT_INSTALLED")
        self.assertEqual(report["blueprint_reference"]["bpc_bpo_unknown_instances"]["BPC"],123)
        self.assertEqual(report["blueprint_reference"]["ordinary_contract_blueprint_type_credits_ignored"],5)

    def test_incomplete_run_never_claimed_complete(self):
        folder=self.make_run(finished=False)
        with self.assertRaisesRegex(ValueError, "RUN_NOT_COMPLETED"):
            inspect_run(folder)
        with self.assertRaisesRegex(ValueError, "NO_COMPLETED_RUNS"):
            latest_folders(self.root)

    def test_latest_completed_selection_ignores_newer_incomplete(self):
        old=self.make_run("20261110T092301Z-good")
        self.make_run("20261110T102301Z-started",finished=False)
        self.assertEqual(latest_folders(self.root,3),[old])

    def test_mismatched_proof_count_fails_closed(self):
        folder=self.make_run()
        report=json.loads((folder/"deep_shadow.json").read_text())
        report["proof_count"]=999
        write_json(folder/"deep_shadow.json",report)
        with self.assertRaisesRegex(ValueError,"PROOF_COUNT_MISMATCH"):
            inspect_run(folder)


if __name__ == "__main__":
    unittest.main()
