"""Offline hot SQLite staging tests: archived old runs required, no live replace."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from v4.local_store import _init
from v4.proof_cold_archive import archive_one, ledger_runs, source_index
from v4.hot_ledger_stage import preview, stage


class HotStageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/"runs").mkdir()
        (self.root/"sqlite").mkdir()
        self.db=self.root/"sqlite"/"v4-shadow.sqlite3"
        with closing(sqlite3.connect(self.db)) as conn:
            _init(conn)
            for i in range(25):
                run_id=f"v4-stage-{i:03}"
                raw=(json.dumps(
                    {"instance":f"market:test:{i:03}","status":"WATCH",
                     "reason":"TEST"})+"\n").encode()
                folder=self.root/"runs"/str(i)
                folder.mkdir()
                (folder/"deep_shadow.json").write_text(
                    json.dumps({"run_id":run_id}),encoding="utf-8")
                (folder/"all_proofs.jsonl").write_bytes(raw)
                conn.execute(
                    "INSERT INTO scan_runs VALUES (?,?,?,?,?,?)",
                    (run_id,"SHADOW_VERIFIED_OFFLINE",1,
                     hashlib.sha256(raw).hexdigest(),
                     json.dumps({"run_id":run_id}),
                     f"2026-10-{i+1:02}T00:00:00+00:00"))
                conn.execute(
                    "INSERT INTO proof_versions VALUES (?,?,?,?,?)",
                    (run_id,f"market:test:{i:03}","WATCH","TEST",
                     json.dumps({"instance":f"market:test:{i:03}"})))
            conn.commit()
        self.original_size=self.db.stat().st_size

    def _archive_oldest(self):
        rec=ledger_runs(self.root)[-1]
        with patch("v4.proof_cold_archive.MIN_FREE_GIB",0):
            archive_one(self.root,rec,source_index(self.root)[rec["run_id"]])
        return rec

    def test_no_stage_without_all_cold_archives(self):
        p=preview(self.root,keep_runs=24)
        self.assertEqual(p["missing_archives"],1)
        self.assertFalse(p["can_stage"])
        with self.assertRaisesRegex(RuntimeError,"ARCHIVES_NOT_COMPLETE"):
            stage(self.root,keep_runs=24)
        self.assertFalse((self.root/"hot-stage").exists())

    def test_staged_database_has_all_metadata_only_recent_proofs(self):
        self._archive_oldest()
        with patch("v4.hot_ledger_stage.MIN_FREE_GIB",0):
            result=stage(self.root,keep_runs=24)
        self.assertEqual(result["status"],"STAGED_NOT_ACTIVATED")
        self.assertEqual(result["cold_verified_runs"],1)
        self.assertEqual(result["hot_proof_rows"],24)
        candidate=Path(result["candidate_db"])
        with closing(sqlite3.connect(candidate)) as db:
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM scan_runs").fetchone()[0],25)
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM proof_versions").fetchone()[0],24)
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0],"ok")
            self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0],"delete")
            self.assertEqual(db.execute("PRAGMA auto_vacuum").fetchone()[0],2)
            self.assertEqual(db.execute(
                "SELECT policy_version,keep_runs,active FROM v4_hot_policy"
                ).fetchone(),(1,24,0))
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM v4_cold_proofs").fetchone()[0],1)
        with closing(sqlite3.connect(self.db)) as original:
            self.assertEqual(original.execute(
                "SELECT COUNT(*) FROM proof_versions").fetchone()[0],25)
        self.assertTrue(self.db.exists())
        self.assertTrue(Path(result["manifest"]).exists())
        self.assertFalse(candidate.with_name(candidate.name+"-wal").exists())

    def test_read_only_cutover_preflight_accepts_sealed_fresh_candidate(self):
        from v4.hot_cutover_preflight import preflight
        self._archive_oldest()
        with patch("v4.hot_ledger_stage.MIN_FREE_GIB",0):
            result=stage(self.root,keep_runs=24)
        decision=preflight(self.root,Path(result["candidate_db"]),
                           verify_hash=True)
        self.assertEqual(decision["status"],
                         "CANDIDATE_READY_FOR_CONTROLLED_MAINTENANCE")
        self.assertTrue(decision["candidate_hash_rechecked"])
        self.assertFalse(decision["cutover_performed"])
        self.assertTrue(self.db.exists())

    def test_read_only_cutover_preflight_blocks_poststage_new_scan(self):
        from v4.hot_cutover_preflight import preflight
        self._archive_oldest()
        with patch("v4.hot_ledger_stage.MIN_FREE_GIB",0):
            result=stage(self.root,keep_runs=24)
        with closing(sqlite3.connect(self.db)) as db:
            db.execute(
                "INSERT INTO scan_runs VALUES (?,?,?,?,?,?)",
                ("v4-new-scan","SHADOW_VERIFIED_OFFLINE",1,
                 "testsha","{}", "2026-10-26T00:00:00Z"))
            db.commit()
        decision=preflight(self.root,Path(result["candidate_db"]))
        self.assertEqual(decision["status"],"NOT_READY")
        self.assertIn("STAGE_STALE_OR_LEDGER_METADATA_CHANGED",
                      decision["problems"])

    def test_corrupt_cold_blocks_stage_and_preserves_source(self):
        record=self._archive_oldest()
        file=self.root/"cold-proof-archives"/(record["run_id"]+".jsonl.gz")
        file.write_bytes(b"bad")
        with patch("v4.hot_ledger_stage.MIN_FREE_GIB",0):
            with self.assertRaisesRegex(RuntimeError,"CHECKSUM_MISMATCH"):
                stage(self.root,keep_runs=24)
        self.assertEqual(len(ledger_runs(self.root)),25)
        self.assertFalse((self.root/"hot-stage").exists())


if __name__=="__main__":
    unittest.main()
