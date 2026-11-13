import json
import sqlite3
import time
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from v4.local_store import persist


class LocalStoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        self.db, self.report, self.proofs = root/"ledger.db", root/"deep.json", root/"proofs.jsonl"
        self.rows = [
            {"instance":"contract:111","status":"RESEARCH","reason":"UNVERIFIED"},
            {"family":"market:1:2:3","instance":None,"status":"WATCH",
             "reason":"NOT_RECHECKED","model_candidate":True},
        ]
        self.write()

    def tearDown(self):
        # SQLite WAL/SHM handles can stay briefly open on Windows while
        # antivirus/indexing inspects files after a connection closes.
        # Retry only WinError 32, with a strict bound; don't hide leaks.
        for attempt in range(12):
            try:
                self.dir.cleanup()
                return
            except PermissionError as exc:
                if getattr(exc, "winerror", None) != 32 or attempt == 11:
                    raise
                time.sleep(0.15)

    def write(self, *, run_id="v4-test-001", expected=None, formal=0):
        self.report.write_text(json.dumps({
            "run_id":run_id, "status":"SHADOW_ONLY_NO_LIVE_ALERTS",
            "proof_count":len(self.rows) if expected is None else expected,
            "formal_candidates":formal,
            "model_candidates":sum(x.get("model_candidate") is True for x in self.rows),
            "reason_counts":{reason:sum(x.get("reason")==reason for x in self.rows)
                             for reason in {x.get("reason") for x in self.rows}},
        }),encoding="utf-8")
        self.proofs.write_text("".join(json.dumps(x)+"\n" for x in self.rows),encoding="utf-8")

    def audit(self):
        return persist(self.db,self.report,self.proofs)

    def test_two_proofs_reconcile_and_retry_idempotently(self):
        a=self.audit()
        b=self.audit()
        self.assertEqual(a["sqlite_unique_proofs"],2)
        self.assertEqual(a["proofs_sha256"],b["proofs_sha256"])
        self.assertFalse(a["mail_enabled"])
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM proof_versions").fetchone()[0],2)
            self.assertEqual(conn.execute("SELECT status FROM scan_runs").fetchone()[0],
                             "SHADOW_VERIFIED_OFFLINE")

    def test_duplicate_instance_rolls_back_whole_run(self):
        self.rows.append(dict(self.rows[0]))
        self.write()
        with self.assertRaisesRegex(ValueError,"DUPLICATE_OR_CONFLICTING_PROOF"):
            self.audit()
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM proof_versions").fetchone()[0],0)

    def test_wrong_expected_count_rolls_back(self):
        self.write(expected=3)
        with self.assertRaisesRegex(ValueError,"ARTIFACT_COUNT_MISMATCH"):
            self.audit()

    def test_mail_is_never_persisted(self):
        self.rows[0]["status"]="MAIL"
        self.write()
        with self.assertRaisesRegex(ValueError,"UNSAFE_SHADOW_PROOF_STATUS"):
            self.audit()

    def test_missing_reason_rejected(self):
        self.rows[0]["reason"]=""
        self.write()
        with self.assertRaisesRegex(ValueError,"MISSING_PROOF_REASON"):
            self.audit()

    def test_same_run_changed_proof_is_blocked(self):
        self.audit()
        self.rows[0]["reason"]="DIFFERENT"
        self.write()
        with self.assertRaisesRegex(ValueError,"DUPLICATE_OR_CONFLICTING_PROOF"):
            self.audit()

    def test_different_run_can_append(self):
        self.audit()
        self.write(run_id="v4-test-002")
        self.audit()
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM scan_runs").fetchone()[0],2)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM proof_versions").fetchone()[0],4)

    def test_nonfinite_json_is_blocked(self):
        self.proofs.write_text('{"instance":"contract:111","status":"WATCH","reason":"ok","profit":NaN}\n',encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"NONFINITE_JSON_TOKEN"):
            self.audit()


if __name__ == "__main__":
    unittest.main()
