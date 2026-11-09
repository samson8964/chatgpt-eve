"""Five-station Windows monitor regressions; no network or scheduler mutations."""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from v4.desktop_status import read_snapshot
from v4.desktop_widget import _structure_lines, _opportunity_text
from v4.structure_registry import HUNTER_ENABLE_CONTENT, HUNTER_FIVE_LANES

LANES = tuple(row[0] for row in HUNTER_FIVE_LANES)


class HunterWidgetTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "runs").mkdir()
        (self.root / "logs").mkdir()
        (self.root / "opportunity-push").mkdir()

    def activate(self, valid=True):
        path = self.root / "config" / "hunter-five-station.enabled"
        path.parent.mkdir()
        path.write_text(HUNTER_ENABLE_CONTENT if valid else "wrong",
                        encoding="utf8")
        return path

    def write_run(self, name, *, status="SHADOW_RECORDED", lanes=LANES,
                  missing=None, partial=None, mtime=None):
        folder = self.root / "runs" / name
        folder.mkdir()
        health = {lane: {"status":"COMPLETE","orders":100,"pages":3,
                         "pages_fetched":3} for lane in lanes}
        if missing:
            health.pop(missing, None)
        if partial:
            health[partial]["pages_fetched"] = 2
        manifest = folder / "manifest.json"
        manifest.write_text(json.dumps({
            "status":status,
            "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
            "source_input_integrity":"ALL_PARSED",
            "structure_health":health,
            "sqlite_unique_proofs":987,
        }), encoding="utf-8")
        (folder / "deep_shadow.json").write_text(json.dumps({
            "model_candidates":8,
            "market_proofs_examined":13,
            "contract_approved_locations_examined":111,
        }), encoding="utf-8")
        if mtime is not None:
            os.utime(manifest, (mtime,mtime))
        return manifest

    def test_newly_enabled_five_station_rejects_old_green_history(self):
        previous = self.write_run("20261109T000000Z-old",lanes=("cj","o4t"))
        marker = self.activate()
        os.utime(previous,(marker.stat().st_mtime-100,
                           marker.stat().st_mtime-100))
        result = read_snapshot(self.root,{"state":"Ready","last_result":0})
        self.assertEqual(result["scan_scope_name"],"HUNTER_FIVE")
        self.assertTrue(result["hunter_enabled"])
        self.assertTrue(result["banestar_enabled"])
        self.assertEqual(result["status"],"WAITING_NEW_SCOPE")
        self.assertEqual(result["scan_scope_status"],"WAITING_NEW_SCOPE")
        self.assertEqual(set(result["structures"]),set(LANES))
        self.assertTrue(all(v=="PENDING_FIRST_RUN"
                            for v in result["structures"].values()))
        self.assertIsNone(result["proofs"])
        self.assertIsNone(result["model_candidates"])
        row1,row2 = _structure_lines(result)
        for label in ("C-J","UALX-3","R-ARKN"):
            self.assertIn(label,row1)
        for label in ("O4T","74L2-U"):
            self.assertIn(label,row2)
        self.assertIn("4-H 已退出",row2)

    def test_latest_complete_five_station_preserves_metrics(self):
        marker=self.activate()
        t=marker.stat().st_mtime+100
        self.write_run("20261109T010000Z-new",mtime=t)
        result=read_snapshot(self.root,{"state":"Ready","last_result":0})
        self.assertEqual(result["status"],"SHADOW_RECORDED")
        self.assertEqual(result["scan_scope_status"],"COMPLETE")
        self.assertEqual(result["proofs"],987)
        self.assertEqual(result["market_examined"],13)
        self.assertEqual(result["contract_examined"],111)
        self.assertEqual(set(result["structure_labels"]),set(LANES))
        self.assertEqual(result["active_lanes"],list(LANES))
        self.assertEqual(_structure_lines(result)[0].count("✓"),3)
        self.assertEqual(_structure_lines(result)[1].count("✓"),2)

    def test_missing_station_cannot_turn_green(self):
        marker=self.activate()
        self.write_run("20261109T010000Z-new",missing="ualx",
                       mtime=marker.stat().st_mtime+100)
        snap=read_snapshot(self.root,{"state":"Ready","last_result":0})
        self.assertEqual(snap["status"],"DEGRADED_PARTIAL_COVERAGE")
        self.assertEqual(snap["structures"]["ualx"],"MISSING")
        self.assertIsNone(snap["model_candidates"])

    def test_single_incomplete_page_cannot_turn_green(self):
        marker=self.activate()
        self.write_run("20261109T010000Z-new",partial="cj",
                       mtime=marker.stat().st_mtime+100)
        snap=read_snapshot(self.root,{"state":"Ready","last_result":0})
        self.assertEqual(snap["status"],"DEGRADED_PARTIAL_COVERAGE")
        self.assertEqual(snap["scan_scope_status"],"INCOMPLETE_COVERAGE")
        self.assertEqual(snap["structures"]["cj"],"INCOMPLETE")
        self.assertIsNone(snap["proofs"])

    def test_failed_newer_run_not_hidden_by_previous_five_success(self):
        marker=self.activate()
        t=marker.stat().st_mtime
        self.write_run("20261109T010000Z-good",mtime=t+20)
        self.write_run("20261109T020000Z-bad",status="FAILED",mtime=t+30)
        snap=read_snapshot(self.root,{"state":"Ready","last_result":1})
        self.assertEqual(snap["status"],"FAILED")
        self.assertEqual(snap["scan_scope_status"],"INCOMPLETE_COVERAGE")
        self.assertIsNone(snap["model_candidates"])

    def test_valid_five_report_while_new_scan_running_uses_last_proof(self):
        marker=self.activate()
        t=marker.stat().st_mtime
        self.write_run("20261109T010000Z-good",mtime=t+20)
        self.write_run("20261109T020000Z-started",status="STARTED",mtime=t+30)
        snap=read_snapshot(self.root,{"state":"Running"})
        self.assertEqual(snap["status"],"RUNNING")
        self.assertEqual(snap["scan_scope_status"],"COMPLETE")
        self.assertEqual(snap["model_candidates"],8)

    def test_scope_marker_not_valid_is_not_five_mode(self):
        self.activate(valid=False)
        self.write_run("20261109T010000Z-legacy",lanes=("cj","o4t"))
        snap=read_snapshot(self.root,{"state":"Ready"})
        self.assertFalse(snap["hunter_enabled"])
        self.assertEqual(snap["active_lanes"],["cj","o4t"])

    def test_old_opportunity_report_not_five_station_success(self):
        marker=self.activate()
        p=self.root/"opportunity-push"/"a.json"
        p.write_text(json.dumps({
            "status":"OPPORTUNITY_NOTIFICATION_CYCLE_COMPLETE",
            "authenticated_structure_health":{
                lane:{"status":"COMPLETE","pages":1} for lane in ("cj","o4t","banestar")},
            "qualified_model_leads":5,
        }),encoding="utf-8")
        os.utime(p,(marker.stat().st_mtime+10,marker.stat().st_mtime+10))
        snap=read_snapshot(self.root,{"state":"Ready"})
        self.assertEqual(snap["opportunity"]["status"],"INCOMPLETE_COVERAGE")
        self.assertIsNone(snap["opportunity"]["qualified_model_leads"])
        detail=_opportunity_text(snap["opportunity"],True,hunter_enabled=True)[1]
        self.assertIn("等待同范围完整报告",detail)

    def test_no_opportunity_data_is_not_claimed_zero(self):
        self.activate()
        snap=read_snapshot(self.root,{"state":"Ready"})
        detail=_opportunity_text(snap["opportunity"],True,hunter_enabled=True)[1]
        self.assertIn("不是零机会",detail)


if __name__=="__main__":
    unittest.main()
