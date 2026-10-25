"""Regression tests for non-destructive, lossless V4 cold proof archives."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from v4.local_store import _init
from v4.proof_cold_archive import (archive_one, ledger_runs, run,
                                   source_index, verify_archive)


class ProofColdArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "sqlite").mkdir()
        (self.root / "runs").mkdir()
        self.db = self.root / "sqlite" / "v4-shadow.sqlite3"
        self.records = []
        with closing(sqlite3.connect(self.db)) as db:
            _init(db)
            for i in range(26):
                run_id = f"v4-test-archive-{i:03}"
                folder = self.root / "runs" / f"202610{i+1:02}-fixture"
                folder.mkdir()
                lines = [
                    json.dumps({"instance":f"contract:{i:03}:001",
                                "status":"WATCH","reason":"FIXTURE"},
                               separators=(",",":")) + "\n",
                    json.dumps({"instance":f"market:{i:03}:002",
                                "status":"RESEARCH","reason":"FIXTURE"},
                               separators=(",",":")) + "\n",
                ]
                raw = "".join(lines).encode()
                source = folder / "all_proofs.jsonl"
                source.write_bytes(raw)
                (folder / "deep_shadow.json").write_text(
                    json.dumps({"run_id":run_id}), encoding="utf-8")
                sha = hashlib.sha256(raw).hexdigest()
                when=f"2026-10-{i+1:02}T00:00:00+00:00"
                db.execute(
                    "INSERT INTO scan_runs VALUES (?,?,?,?,?,?)",
                    (run_id,"SHADOW_VERIFIED_OFFLINE",2,sha,"{}",when))
                self.records.append({"run_id":run_id,
                                     "status":"SHADOW_VERIFIED_OFFLINE",
                                     "proof_count":2,
                                     "proof_sha256":sha,
                                     "audited_at":when})
            db.commit()

    def test_default_coverage_does_not_change_originals(self):
        output=run(self.root,keep_runs=24)
        self.assertEqual(output["status"],"READ_ONLY_COVERAGE")
        self.assertEqual(output["cold_run_candidates"],2)
        self.assertEqual(output["missing_raw_source_count"],0)
        self.assertFalse((self.root/"cold-proof-archives").exists())
        self.assertEqual(len(ledger_runs(self.root)),26)

    def test_roundtrip_one_and_idempotent_verify(self):
        with patch("v4.proof_cold_archive.MIN_FREE_GIB",0):
            report=run(self.root,apply=True,keep_runs=24,limit=1)
        self.assertEqual(report["status"],"ARCHIVE_RUN_COMPLETE")
        self.assertEqual(report["archived_this_call"],1)
        oldest=self.records[0]
        verified=verify_archive(self.root,oldest)
        self.assertEqual(verified["proof_count"],2)
        self.assertEqual(len(ledger_runs(self.root)),26)
        with patch("v4.proof_cold_archive.MIN_FREE_GIB",0):
            retry=run(self.root,apply=True,keep_runs=24,limit=1)
        self.assertEqual(retry["verified_existing"],1)
        self.assertEqual(retry["archived_this_call"],0)

    def test_corrupted_source_blocks_publication(self):
        record=self.records[0]
        source=source_index(self.root)[record["run_id"]]
        source.write_bytes(b"changed\n")
        with patch("v4.proof_cold_archive.MIN_FREE_GIB",0):
            result=run(self.root,apply=True,keep_runs=24,limit=1)
        self.assertEqual(result["status"],"PARTIAL_BLOCKED")
        self.assertEqual(result["archived_this_call"],0)
        folder=self.root/"cold-proof-archives"
        self.assertFalse((folder/(record["run_id"]+".manifest.json")).exists())
        self.assertTrue(self.db.exists())

    def test_corrupted_archive_is_never_treated_as_verified(self):
        rec=self.records[0]
        with patch("v4.proof_cold_archive.MIN_FREE_GIB",0):
            archive_one(self.root,rec,source_index(self.root)[rec["run_id"]])
        folder=self.root/"cold-proof-archives"
        (folder/(rec["run_id"]+".jsonl.gz")).write_bytes(b"bad")
        with self.assertRaisesRegex(RuntimeError,"CHECKSUM_MISMATCH"):
            verify_archive(self.root,rec)
        with patch("v4.proof_cold_archive.MIN_FREE_GIB",0):
            result=run(self.root,apply=True,keep_runs=24,limit=1)
        self.assertEqual(result["status"],"PARTIAL_BLOCKED")

    def test_missing_raw_source_is_reported_not_deleted(self):
        rec=self.records[0]
        source_index(self.root)[rec["run_id"]].unlink()
        coverage=run(self.root,keep_runs=24)
        self.assertEqual(coverage["missing_raw_source_count"],1)
        with patch("v4.proof_cold_archive.MIN_FREE_GIB",0):
            out=run(self.root,apply=True,keep_runs=24,limit=1)
        self.assertEqual(out["status"],"PARTIAL_BLOCKED")
        self.assertEqual(out["archived_this_call"],1)  # Next oldest is still available.
        self.assertEqual(len(ledger_runs(self.root)),26)

    def test_source_coverage_requires_proven_complete_ledger(self):
        with self.assertRaisesRegex(ValueError,"KEEP_RUNS"):
            run(self.root,keep_runs=12)
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("UPDATE scan_runs SET status='IMPORTING' WHERE run_id=?",
                       (self.records[0]["run_id"],))
            db.commit()
        out=run(self.root,keep_runs=24)
        self.assertEqual(out["unverified_run_count"],1)


if __name__=="__main__":
    unittest.main()
