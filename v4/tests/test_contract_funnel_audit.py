"""Offline contract research mail-funnel regression and crystal screen diagnostic."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v4.contract_funnel_audit import audit, audit_folder

RUN="20261016T122301Z-example"


def make_run(root, *, crystal_share, valid=True, profit=90_000_000):
    folder=root/"runs"/RUN
    folder.mkdir(parents=True)
    (folder/"manifest.json").write_text(json.dumps({
        "status":"SHADOW_RECORDED",
        "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
        "source_input_integrity":"ALL_PARSED"}))
    (folder/"full_market_report.json").write_text(
        json.dumps({"contracts":{"contract_rows_total":50000}}))
    (folder/"deep_shadow.json").write_text(
        json.dumps({"contract_approved_locations_examined":43000,
                    "contract_requested_items_excluded":4,
                    "contract_crystal_screen_basis":"JITA_BUY_DEPTH_BY_INVENTORY_GROUP"}))
    good={
        "kind":"contract","reason":"LIVE_ORDER_AND_CONTRACT_NOT_REVALIDATED",
        "model_candidate":True,"status":"WATCH",
        "valuation_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE",
        "valuation_location_id":60003760,"destination_location":60003760,
        "contract_id":123,"source_location":60008494,
        "included_items":{"34":10},"net_profit":profit,
        "roi":.25,"cost":360_000_000,"stress_profit":25_000_000,
        "energy_crystal_value_share":crystal_share,
    }
    if not valid:
        good["reason"]="PARTIAL_CASH_FLOOR_RESEARCH"
        good["net_profit"]=None
    (folder/"all_proofs.jsonl").write_text(json.dumps(good)+"\n")
    return folder


class ContractFunnelAuditTests(unittest.TestCase):
    def test_unknown_crystal_isolated_from_normal_profit(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            d=make_run(root,crystal_share=None)
            row=audit_folder(d)
            self.assertEqual(row["contract_public_archive_rows"],50000)
            self.assertEqual(row["contract_proofs_found"],1)
            self.assertEqual(row["count_qualifying_50m_roi_stress_BEFORE_crystal_filter"],1)
            self.assertEqual(row["count_qualifying_AFTER_crystal_filter"],0)
            self.assertEqual(row["among_basic_qualifiers_crystal_unknown"],1)
            self.assertEqual(row["rejected_only_by_crystal_filter"],1)
            self.assertFalse(row["gmail_receipt_present"])
            self.assertEqual(audit(root)["run_count"],1)

    def test_majority_crystal_excluded_ordinary_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            d=make_run(root,crystal_share=.7)
            row=audit_folder(d)
            self.assertEqual(row["among_basic_qualifiers_crystal_majority"],1)
            self.assertEqual(row["count_qualifying_AFTER_crystal_filter"],0)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            d=make_run(root,crystal_share=0.0)
            row=audit_folder(d)
            self.assertEqual(row["among_basic_qualifiers_crystal_below_half"],1)
            self.assertEqual(row["count_qualifying_AFTER_crystal_filter"],1)

    def test_missing_net_is_upstream_valuation_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            row=audit_folder(make_run(Path(td),crystal_share=None,valid=False))
            self.assertEqual(row["contract_proofs_without_computed_net"],1)
            self.assertEqual(row["count_qualifying_50m_roi_stress_BEFORE_crystal_filter"],0)
            self.assertEqual(row["contract_reason_counts"]["PARTIAL_CASH_FLOOR_RESEARCH"],1)

    def test_under_50m_not_crystal_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            row=audit_folder(make_run(Path(td),crystal_share=None,profit=40_000_000))
            self.assertEqual(row["count_qualifying_50m_roi_stress_BEFORE_crystal_filter"],0)
            self.assertEqual(row["count_qualifying_AFTER_crystal_filter"],0)
            self.assertEqual(row["rejected_only_by_crystal_filter"],0)


if __name__ == "__main__":
    unittest.main()
