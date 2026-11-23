"""Offline classification audit: distinguish actual blueprints from catalogue misses."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v4.catalog import Catalog
from v4.contract_classification_audit import analyze


class ContractClassificationAuditTests(unittest.TestCase):
    def test_classify_reason_without_guessing_blueprint_copy_or_unknown_type(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            meta={"catalog_meta":{"sha256":"same"}}
            (folder/"deep_shadow.json").write_text(json.dumps(meta))
            lines=[]
            def add(cid,inc,reason="ITEM_CLASSIFICATION_UNVERIFIED_OR_BLUEPRINT",
                    net=None,roi=None,stress=None,blueprints=None):
                lines.append(json.dumps({
                    "kind":"contract","contract_id":cid,"reason":reason,
                    "included_items":inc,
                    "contract_blueprint_evidence":blueprints or {},
                    "net_profit":net,"roi":roi,"stress_profit":stress
                }))
            add(1,{"101":1},blueprints={"BPC":1})
            add(2,{"102":1})
            add(3,{"103":1})
            add(4,{"104":1})
            add(5,{"102":2},"BELOW_GATE_OR_STRESS",net=80_000_000,
                roi=.05,stress=-10_000_000)
            add(6,{"102":2},"BELOW_GATE_OR_STRESS",net=100_000_000,
                roi=.12,stress=1)
            (folder/"all_proofs.jsonl").write_text("\n".join(lines)+"\n")
            catalog=Catalog(items={
                "101":[1,"blueprint_type",9],
                "102":[1,"regular",10],
                "103":[1,"unknown",None],
                "104":[1,"regular",11]
            },meta={"sha256":"same"})
            report=analyze(folder,catalog)
            self.assertEqual(report["classification_rejects_expected"],4)
            self.assertEqual(report["classification_rejects_explained"],4)
            self.assertEqual(report["classification_reject_categories"][
                "HAS_BLUEPRINT_ITEM_TYPE"],1)
            self.assertEqual(report["classification_reject_categories"][
                "HAS_UNKNOWN_ITEM_TYPE"],1)
            self.assertEqual(report["classification_reject_categories"][
                "ALL_REGULAR_UNEXPECTED_CLASS_REJECT"],2)
            self.assertEqual(report["cash_valuation"]["net_50m_and_roi_10_percent"],1)
            self.assertEqual(report["cash_valuation"][
                "net_50m_and_roi_10_percent_and_stress_positive"],1)
            self.assertTrue(report["catalogue_matches_scan_sha256"])

    def test_current_catalog_missing_report_is_not_fabricated(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            (folder/"deep_shadow.json").write_text("{}")
            (folder/"all_proofs.jsonl").write_text(json.dumps({
                "kind":"contract","contract_id":2,
                "reason":"ITEM_CLASSIFICATION_UNVERIFIED_OR_BLUEPRINT",
                "included_items":{"101":1}})+"\n")
            report=analyze(folder,None)
            self.assertFalse(report["cached_catalog_present"])
            self.assertIsNone(report["catalogue_matches_scan_sha256"])
            self.assertEqual(report["classification_reject_categories"][
                "NO_CATALOG_AVAILABLE"],1)


if __name__=="__main__":
    unittest.main()
