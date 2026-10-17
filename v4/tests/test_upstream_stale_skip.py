"""Expected EVE Ref publishing delays: no stale scans, stale mail or red crash.

Offline regression covering all seams: source -> full census -> local scan
manifest -> scheduled service -> desktop widget. Heavy Pandas/Requests tests
are skipped only in the lightweight (no third-party-deps) reliability suite.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from v4.local_run import run as local_run
from v4.local_service import execute as local_execute, main as service_main
from v4.desktop_status import read_snapshot
from v4.desktop_widget import _status_style

try:
    from v4.sources import advertised, SnapshotStale, SourceError
    from v4.full_scan import run as census_run, main as census_main
except ImportError:
    advertised=SnapshotStale=SourceError=census_run=census_main=None


@unittest.skipUnless(SnapshotStale is not None,"requires full Pandas/Requests runtime")
class UpstreamSourceTests(unittest.TestCase):
    def test_old_market_source_preserves_2h_limit(self):
        now=datetime.now(timezone.utc)
        stale=(now-timedelta(hours=6)).isoformat()
        response=Mock()
        response.json.return_value={"files":[
            {"url":"https://data.everef.net/market-orders/old.bz2",
             "last_modified":stale}]}
        with patch("v4.sources._get",return_value=response):
            with self.assertRaises(SnapshotStale) as cm:
                advertised("https://example.invalid/index",max_age_hours=2)
        self.assertAlmostEqual(cm.exception.age_hours,6,delta=.1)
        self.assertEqual(cm.exception.threshold_hours,2)
        self.assertIn("STALE_SNAPSHOT:",str(cm.exception))
        self.assertEqual(cm.exception.last_modified,stale)

    def test_future_clock_skew_is_real_failure_not_publication_delay(self):
        future=(datetime.now(timezone.utc)+timedelta(hours=3)).isoformat()
        response=Mock()
        response.json.return_value={"files":[
            {"url":"https://data.everef.net/test.bz2","last_modified":future}]}
        with patch("v4.sources._get",return_value=response):
            with self.assertRaisesRegex(SourceError,"CLOCK_SKEW") as cm:
                advertised("https://example.invalid/index",max_age_hours=2)
        self.assertNotIsInstance(cm.exception,SnapshotStale)

    def test_one_fresh_one_stale_does_not_download_or_use_old_cache(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            market={"url":"https://data.everef.net/new-market.bz2",
                    "last_modified":"2026-10-18T00:00:00Z","age_hours":.2}
            late=SnapshotStale(5.86,3,"2026-10-17T18:00:00Z")
            with patch("v4.full_scan.advertised",side_effect=[market,late]) as ad, \
                 patch("v4.full_scan.download_fresh") as downloaded:
                result=census_run(root/"report.json",root/"raw")
            self.assertEqual(result["overall"],"SKIPPED_UPSTREAM_STALE")
            self.assertEqual(ad.call_count,2)
            downloaded.assert_not_called()
            self.assertEqual(result["sources"]["market_orders"]["status"],
                             "FRESH_ADVERTISED")
            self.assertEqual(result["sources"]["public_contracts"]["status"],"STALE")
            self.assertAlmostEqual(result["sources"]["public_contracts"]["age_hours"],5.86)
            self.assertFalse((root/"raw").exists())
            self.assertEqual(json.loads((root/"report.json").read_text())["overall"],
                             "SKIPPED_UPSTREAM_STALE")

    def test_two_stale_snapshots_are_not_scanned_or_mailed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with patch("v4.full_scan.advertised",side_effect=[
                SnapshotStale(6.03,2,"2026-10-17T14:00:00Z"),
                SnapshotStale(5.86,3,"2026-10-17T14:11:00Z"),
            ]),patch("v4.full_scan.download_fresh") as downloader:
                outcome=census_run(root/"report.json",root/"raw")
            downloader.assert_not_called()
            self.assertEqual(outcome["overall"],"SKIPPED_UPSTREAM_STALE")
            self.assertEqual([x["status"] for x in outcome["sources"].values()],
                             ["STALE","STALE"])
            # CLI must signal an intentionally skipped cycle with exit 0.
            with patch("v4.full_scan.run",return_value=outcome), \
                 patch("sys.argv",["v4.full_scan"]),redirect_stdout(StringIO()):
                census_main()

    def test_real_index_failure_still_fails_and_census_exit_nonzero(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with patch("v4.full_scan.advertised",side_effect=[
                SnapshotStale(6.03,2,"old"),SourceError("SOURCE_FETCH_FAILED")
            ]),patch("v4.full_scan.download_fresh") as downloader:
                outcome=census_run(root/"report.json",root/"raw")
            downloader.assert_not_called()
            self.assertEqual(outcome["overall"],"FAILED_SOURCE_COVERAGE")
            self.assertEqual(outcome["sources"]["public_contracts"]["status"],"FAILED")
            with patch("v4.full_scan.run",return_value=outcome), \
                 patch("sys.argv",["v4.full_scan"]),redirect_stdout(StringIO()):
                with self.assertRaises(SystemExit):
                    census_main()


class LocalStaleSkipTests(unittest.TestCase):
    def test_local_run_writes_skip_manifest_without_deep_scan_or_sqlite(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            existing=root/"sqlite"/"v4-shadow.sqlite3"
            existing.parent.mkdir(parents=True)
            existing.write_bytes(b"EXISTING_SQLITE_NOT_MODIFIED")
            stages=[]
            def fake_step(stage,commands,run_dir,cwd,**kwargs):
                stages.append(stage)
                self.assertEqual(stage,"full_scan")
                target=Path(commands[commands.index("--output")+1])
                target.write_text(json.dumps({
                    "overall":"SKIPPED_UPSTREAM_STALE",
                    "sources":{
                        "market_orders":{"status":"STALE",
                                         "age_hours":6.03,"threshold_hours":2},
                        "public_contracts":{"status":"STALE",
                                            "age_hours":5.86,"threshold_hours":3}},
                }),encoding="utf-8")
            with patch("v4.local_run._step",side_effect=fake_step):
                result=local_run(root)
            self.assertEqual(stages,["full_scan"])
            self.assertEqual(result["status"],"SKIPPED_UPSTREAM_STALE")
            self.assertFalse(result["mail_enabled"])
            self.assertEqual(existing.read_bytes(),b"EXISTING_SQLITE_NOT_MODIFIED")
            latest=sorted((root/"runs").iterdir())[-1]
            self.assertFalse((latest/"all_proofs.jsonl").exists())
            self.assertFalse((latest/"deep_shadow.json").exists())
            manifest=json.loads((latest/"manifest.json").read_text())
            self.assertEqual(manifest["status"],"SKIPPED_UPSTREAM_STALE")
            self.assertEqual(manifest["source_input_integrity"],"NOT_DOWNLOADED")

    def test_service_intentional_skip_has_exit_zero_and_sends_no_mail(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            skip={"status":"SKIPPED_UPSTREAM_STALE",
                  "mail_enabled":False,
                  "run_folder":str(root/"runs"/"stale"),
                  "upstream_sources":{"market_orders":{"status":"STALE"}}}
            with patch("v4.local_service.storage_check",return_value={
                    "free_gib":300,"enough_space":True}), \
                 patch("v4.local_service.backup") as backup:
                result=local_execute(root,scanner=lambda _:skip,backup_fn=backup)
                backup.assert_not_called()
            self.assertEqual(result["status"],"SKIPPED_UPSTREAM_STALE")
            self.assertFalse(result["mail_enabled"])
            with patch("sys.argv",["v4.local_service","--data-root",str(root)]), \
                 patch("v4.local_service.execute",return_value=result), \
                 patch("v4.research_mail.send_review") as gmail, \
                 patch("v4.game_mail_review.send_review_to_game") as game:
                code=service_main()
            self.assertEqual(code,0)
            gmail.assert_not_called()
            game.assert_not_called()
            log=(root/"logs"/"shadow-task.log").read_text()
            self.assertIn('"status": "SKIPPED_UPSTREAM_STALE"',log)
            self.assertIn("RESEARCH_MAIL_SKIPPED UPSTREAM_SNAPSHOT_STALE",log)
            self.assertNotIn("FAILED RuntimeError",log)

    def test_tray_shows_amber_expected_skip_and_preserves_previous_success(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            old=root/"runs"/"20261017T182301Z-good"
            new=root/"runs"/"20261017T202301Z-stale"
            old.mkdir(parents=True)
            new.mkdir(parents=True)
            (old/"manifest.json").write_text(json.dumps({
                "status":"SHADOW_RECORDED",
                "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
                "sqlite_unique_proofs":60000,
                "structure_health":{"four_h":{"status":"COMPLETE"},
                                    "cj":{"status":"COMPLETE"},
                                    "o4t":{"status":"COMPLETE"}},
            }))
            (old/"deep_shadow.json").write_text(json.dumps({
                "market_proofs_examined":120,
                "contract_approved_locations_examined":43000,
                "model_candidates":76}))
            (new/"manifest.json").write_text(json.dumps({
                "status":"SKIPPED_UPSTREAM_STALE",
                "upstream_sources":{"market_orders":{"status":"STALE"}},
            }))
            log=root/"logs"/"shadow-task.log"
            log.parent.mkdir()
            log.write_text(
                'START 2026-10-17T20:23:01+00:00\n'
                'RESULT '+json.dumps({
                    "status":"SKIPPED_UPSTREAM_STALE",
                    "run_folder_name":new.name})+'\n')
            info=read_snapshot(root,{"state":"Ready","last_result":0})
            self.assertEqual(info["status"],"SKIPPED_UPSTREAM_STALE")
            self.assertEqual(info["latest_result_status"],"SKIPPED_UPSTREAM_STALE")
            self.assertEqual(info["last_completed_folder"],old.name)
            self.assertEqual(info["market_examined"],120)
            self.assertEqual(info["contract_examined"],43000)
            self.assertEqual(info["structures"]["four_h"],"COMPLETE")
            self.assertEqual(_status_style(info["status"]),
                             ("上游数据尚未更新","amber"))


if __name__=="__main__":
    unittest.main()
