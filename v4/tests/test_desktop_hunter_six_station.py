"""Six-station HY-RWO desktop, contract and stale-scope regression."""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from v4.desktop_status import read_snapshot
from v4.desktop_widget import (
    _structure_lines, _contract_source_lines, _opportunity_text)
from v4.desktop_station_monitor import read_opportunity
from v4.contract_station_monitor import station_contract_summary
from v4.structure_registry import (
    HUNTER_ENABLE_CONTENT, HY_RWO_ENABLE_CONTENT, HY_RWO_LANE,
    HUNTER_FIVE_LANES,
)

FIVE = tuple(row[0] for row in HUNTER_FIVE_LANES)
SIX = FIVE + ("hy_rwo",)


class SixStationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "runs").mkdir()
        (self.root / "logs").mkdir()
        (self.root / "opportunity-push").mkdir()
        (self.root / "config").mkdir()

    def enable(self, *, hy=True):
        five = self.root / "config" / "hunter-five-station.enabled"
        five.write_text(HUNTER_ENABLE_CONTENT, encoding="utf-8")
        hy_path = self.root / "config" / "hunter-hy-rwo.enabled"
        if hy:
            hy_path.write_text(HY_RWO_ENABLE_CONTENT, encoding="utf-8")
        return hy_path if hy else five

    def run_folder(self, label, *, lanes, when, pages_missing=None):
        folder = self.root / "runs" / label
        folder.mkdir()
        health = {lane: {
            "status": "COMPLETE", "pages": 2, "pages_fetched": 2,
            "orders": 11,
        } for lane in lanes}
        if pages_missing:
            health[pages_missing]["pages_fetched"] = 1
        manifest = folder / "manifest.json"
        manifest.write_text(json.dumps({
            "status": "SHADOW_RECORDED",
            "coverage_gate": "INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
            "structure_health": health,
            "sqlite_unique_proofs": 800,
        }), encoding="utf-8")
        (folder / "deep_shadow.json").write_text(json.dumps({
            "model_candidates": 5, "market_proofs_examined": 17,
            "contract_approved_locations_examined": 201,
        }), encoding="utf-8")
        os.utime(manifest, (when, when))
        return folder

    def test_sixth_marker_required_and_old_five_proofs_rejected(self):
        marker = self.enable(hy=False)
        self.assertEqual(read_snapshot(self.root, {"state":"Ready"})[
                         "scan_scope_name"], "HUNTER_FIVE")
        old = self.run_folder("20261110T030000Z-old", lanes=FIVE,
                              when=time.time()-50)
        hy = self.root / "config" / "hunter-hy-rwo.enabled"
        hy.write_text(HY_RWO_ENABLE_CONTENT, encoding="utf-8")
        snap = read_snapshot(self.root, {"state":"Ready", "last_result":0})
        self.assertEqual(snap["scan_scope_name"], "HUNTER_SIX")
        self.assertEqual(snap["active_lanes"], list(SIX))
        self.assertEqual(snap["scan_scope_status"], "WAITING_NEW_SCOPE")
        self.assertIsNone(snap["model_candidates"])
        self.assertIsNone(snap["private_market_orders"])
        self.assertEqual(snap["structures"]["hy_rwo"], "PENDING_FIRST_RUN")
        self.assertIn("HY-RWO", _structure_lines(snap)[1])
        self.assertIn("六站合同", _contract_source_lines(snap)[1])

    def test_all_six_complete_and_hy_contract_visible(self):
        mark = self.enable()
        future = mark.stat().st_mtime + 90
        folder = self.run_folder("20261110T040000Z-new",
                                 lanes=SIX, when=future)
        summary = station_contract_summary(
            [HY_RWO_LANE[2], HY_RWO_LANE[2], 60008494],
            [{"kind":"contract", "source_location":HY_RWO_LANE[2],
              "model_candidate":True}],
            structures={lane:(loc,profile)
                        for lane,label,loc,profile in
                        HUNTER_FIVE_LANES+(HY_RWO_LANE,)})
        report = json.loads((folder/"deep_shadow.json").read_text("utf-8"))
        report["contract_station_summary"] = summary
        (folder/"deep_shadow.json").write_text(
            json.dumps(report), encoding="utf-8")
        snap = read_snapshot(self.root, {"state":"Ready","last_result":0})
        self.assertEqual(snap["scan_scope_status"], "COMPLETE")
        self.assertEqual(snap["structures"]["hy_rwo"], "COMPLETE")
        self.assertEqual(snap["private_market_orders"], 66)
        self.assertEqual(snap["private_market_pages"], 12)
        self.assertEqual(snap["proofs"], 800)
        self.assertTrue(snap["hy_rwo_enabled"])
        self.assertIn("HY-RWO ✓", _structure_lines(snap)[1])
        header, structures, npc = _contract_source_lines(snap)
        self.assertIn("HY-RWO 1/2", structures)
        self.assertEqual(summary["stations"]["hy_rwo"]["location_id"],
                         1049633275448)
        self.assertEqual(len(summary["stations"]), 8)

    def test_one_missing_page_blocks_six_success(self):
        marker = self.enable()
        self.run_folder("20261110T040000Z-new", lanes=SIX,
                        when=marker.stat().st_mtime+90,
                        pages_missing="hy_rwo")
        snap = read_snapshot(self.root, {"state":"Ready","last_result":0})
        self.assertEqual(snap["scan_scope_status"], "INCOMPLETE_COVERAGE")
        self.assertEqual(snap["structures"]["hy_rwo"], "INCOMPLETE")
        self.assertIsNone(snap["model_candidates"])
        self.assertIsNone(snap["private_market_orders"])

    def test_five_station_opportunity_report_cannot_certify_six(self):
        marker = self.enable()
        p = self.root / "opportunity-push" / "sample.json"
        p.write_text(json.dumps({
            "status": "OPPORTUNITY_NOTIFICATION_CYCLE_COMPLETE",
            "authenticated_structure_health": {
                lane: {"status":"COMPLETE", "pages":2, "pages_fetched":2}
                for lane in FIVE},
            "qualified_model_leads": 5,
        }), encoding="utf-8")
        os.utime(p, (marker.stat().st_mtime+40,)*2)
        out = read_opportunity(self.root, SIX, marker.stat().st_mtime)
        self.assertEqual(out["status"], "INCOMPLETE_COVERAGE")
        detail = _opportunity_text(out, True,
                                   hunter_enabled=True,
                                   hy_rwo_enabled=True)[1]
        self.assertIn("六站机会",detail)
        self.assertIn("等待同范围完整报告",detail)


if __name__ == "__main__":
    unittest.main()
