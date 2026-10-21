"""No-network four-station Windows widget regressions, including stale-evidence guard."""
from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from v4.desktop_station_monitor import read_opportunity, BASE_NAMES, BANESTAR
from v4.desktop_status import read_snapshot
from v4.desktop_widget import _opportunity_text, _channel_label, _station_symbol


class FourStationWidgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runs = self.root / "runs"
        self.runs.mkdir()
        (self.root / "logs").mkdir()
        (self.root / "opportunity-push").mkdir()

    def write_run(self, name, health, *, modified=None):
        folder = self.runs / name
        folder.mkdir()
        file = folder / "manifest.json"
        file.write_text(json.dumps({
            "status": "SHADOW_RECORDED",
            "coverage_gate": "INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
            "structure_health": health,
            "sqlite_unique_proofs": 12,
        }), encoding="utf-8")
        (folder / "deep_shadow.json").write_text(
            '{"model_candidates":12,"market_proofs_examined":24}',
            encoding="utf-8",
        )
        if modified is not None:
            import os
            os.utime(file, (modified, modified))
        return file

    def enable(self):
        marker = self.root / "config" / "banestar-market.enabled"
        marker.parent.mkdir()
        marker.write_text("APPROVED_1050474463169", encoding="ascii")
        return marker

    def health(self, fourth=False):
        rows = {
            name: {"status": "COMPLETE", "orders": 20, "pages": 1,
                   "pages_fetched": 1}
            for name in BASE_NAMES
        }
        if fourth:
            rows[BANESTAR] = {"status": "COMPLETE", "orders": 1634,
                              "pages": 2, "pages_fetched": 2}
        return rows

    def write_opportunity(self, *, four=True, status="OPPORTUNITY_NOTIFICATION_CYCLE_COMPLETE"):
        report = {
            "status": status,
            "finished_at": "2026-10-21T12:30:00+00:00",
            "authenticated_structure_health": self.health(four),
            "by_station": {"74L2-U": {
                "sell_types":1049, "PREFILTER_PASSED":11,
                "MODEL_PASS_RESEARCH_ONLY":3,
            }},
            "qualified_model_leads": 9,
            "notification_channels": {
                "game": {"status":"GAME_MAIL_SENT","sent":True},
                "gmail": {"status":"NO_NEW_QUALIFIED_LEADS","sent":False},
            },
        }
        path = self.root / "opportunity-push" / "20261021T123000Z-test.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    def test_existing_three_station_mode_remains_valid(self):
        self.write_run("20261014T060000Z-abc", self.health())
        snapshot = read_snapshot(self.root, {"state": "Ready", "last_result": 0})
        self.assertFalse(snapshot["banestar_enabled"])
        self.assertEqual(snapshot["scan_scope_status"], "COMPLETE")
        self.assertEqual(snapshot["structures"],
                         {name:"COMPLETE" for name in BASE_NAMES})
        self.assertNotIn("banestar", snapshot["structures"])

    def test_old_green_three_station_report_never_claims_four_station_success(self):
        old = self.write_run("20261014T060000Z-abc", self.health())
        marker = self.enable()
        older = marker.stat().st_mtime - 100
        import os
        os.utime(old, (older, older))
        snapshot = read_snapshot(self.root, {"state": "Ready", "last_result": 0})
        self.assertTrue(snapshot["banestar_enabled"])
        self.assertEqual(snapshot["status"], "WAITING_NEW_SCOPE")
        self.assertEqual(snapshot["latest_result_status"], "WAITING_NEW_SCOPE")
        self.assertTrue(all(v=="PENDING_FIRST_RUN"
                            for v in snapshot["structures"].values()))
        self.assertEqual(snapshot["opportunity"]["status"], "WAITING_FIRST_CYCLE")
        self.assertEqual(_station_symbol(snapshot["structures"]["banestar"]), "…")

    def test_four_station_complete_and_funnel_plus_mail(self):
        marker = self.enable()
        now = marker.stat().st_mtime + 100
        self.write_run("20261021T123000Z-new", self.health(True), modified=now)
        opportunity = self.write_opportunity()
        import os
        os.utime(opportunity, (now, now))
        snapshot = read_snapshot(self.root, {"state":"Ready","last_result":0})
        self.assertEqual(snapshot["status"], "SHADOW_RECORDED")
        self.assertEqual(snapshot["scan_scope_status"], "COMPLETE")
        self.assertEqual(snapshot["structures"]["banestar"], "COMPLETE")
        op = snapshot["opportunity"]
        self.assertEqual(op["status"], "COMPLETE")
        self.assertEqual(op["qualified_model_leads"], 9)
        self.assertEqual(op["station"]["sell_types"], 1049)
        header, station, mail = _opportunity_text(op, True)
        self.assertIn("合格 9", header)
        self.assertIn("1,049", station)
        self.assertIn("初筛 11", station)
        self.assertIn("合格 3", station)
        self.assertIn("游戏 已发送", mail)
        self.assertIn("Gmail 无新机会", mail)

    def test_incomplete_fourth_station_blocks_green_scan(self):
        marker = self.enable()
        now = marker.stat().st_mtime + 100
        self.write_run("20261021T123000Z-new", self.health(), modified=now)
        snapshot = read_snapshot(self.root, {"state":"Ready","last_result":0})
        self.assertEqual(snapshot["structures"]["banestar"], "MISSING")
        self.assertEqual(snapshot["status"], "DEGRADED_PARTIAL_COVERAGE")
        self.assertEqual(snapshot["scan_scope_status"], "INCOMPLETE_COVERAGE")

    def test_old_opportunity_report_does_not_count_after_activation(self):
        old = self.write_opportunity()
        marker = self.enable()
        import os
        older = marker.stat().st_mtime - 100
        os.utime(old,(older,older))
        snapshot = read_opportunity(
            self.root, BASE_NAMES + (BANESTAR,), marker.stat().st_mtime)
        self.assertEqual(snapshot["status"],"WAITING_FIRST_CYCLE")
        self.assertIsNone(snapshot["station"])

    def test_post_activation_three_station_opportunity_cannot_fake_four(self):
        marker=self.enable()
        report=self.write_opportunity(four=False)
        import os
        now=marker.stat().st_mtime+100
        os.utime(report,(now,now))
        value=read_opportunity(
            self.root,BASE_NAMES+(BANESTAR,),marker.stat().st_mtime)
        self.assertEqual(value["status"],"INCOMPLETE_COVERAGE")
        self.assertIsNone(value["qualified_model_leads"])
        self.assertIn("并非零机会",_opportunity_text(value,True)[2])

    def test_new_failed_scan_cannot_reuse_previous_four_station_success(self):
        marker = self.enable()
        t = marker.stat().st_mtime
        self.write_run("20261021T120000Z-valid", self.health(True),
                       modified=t+50)
        broken = self.runs / "20261021T130000Z-failed"
        broken.mkdir()
        manifest = broken / "manifest.json"
        manifest.write_text('{"status":"FAILED","reason":"connection"}',
                            encoding="utf-8")
        import os
        os.utime(manifest, (t+100,t+100))
        snap = read_snapshot(self.root, {"state":"Ready","last_result":1})
        self.assertEqual(snap["status"],"FAILED")
        self.assertEqual(snap["scan_scope_status"],"INCOMPLETE_COVERAGE")
        self.assertEqual(snap["structures"]["banestar"],"MISSING")

    def test_opportunity_report_stale_not_current_and_no_mail_claim(self):
        marker = self.enable()
        p = self.write_opportunity()
        import os
        now = time.time()
        os.utime(marker, (now - 6*3600, now - 6*3600))
        os.utime(p, (now - 4*3600, now - 4*3600))
        result = read_opportunity(
            self.root, BASE_NAMES + (BANESTAR,), marker.stat().st_mtime)
        self.assertEqual(result["status"], "STALE_REPORT")
        header, detail, mail = _opportunity_text(result, True)
        self.assertIn("已过期",header)
        self.assertIn("过期历史结果",detail)
        self.assertIn("并非零机会",mail)

    def test_untrusted_mail_channel_status_is_not_displayed(self):
        self.assertEqual(_channel_label("OPPORTUNITY_CHANNEL_FAILED"),"发送失败")
        self.assertEqual(_channel_label("SENSITIVE_TOKEN"),"未确认")
        self.assertEqual(_station_symbol("FAILED"),"✕")
        self.assertEqual(_station_symbol("UNKNOWN"),"—")

    def test_disabled_flag_bad_contents_does_not_activate(self):
        file=self.enable()
        file.write_text("APPROVE_SOME_OTHER_STRUCTURE",encoding="ascii")
        self.write_run("20261014T060000Z-abc", self.health())
        snap=read_snapshot(self.root, {"state":"Ready"})
        self.assertFalse(snap["banestar_enabled"])
        self.assertNotIn("banestar",snap["structures"])


if __name__ == "__main__":
    unittest.main()
