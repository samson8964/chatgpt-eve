"""Temporary fixture tests for guarded V4 hot-ledger switchover.

All tests run in temporary folders; never reference user's production data.
"""
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from v4.hot_cutover import ACK, _task_disabled, activate, inspect
from v4.hot_ledger_stage import stage
from v4.local_store import _init
from v4.proof_cold_archive import archive_one, ledger_runs, source_index


class CutoverTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sandbox=Path(self.tmp.name)
        self.root=self.sandbox/"data"
        (self.root/"runs").mkdir(parents=True)
        (self.root/"sqlite").mkdir()
        self.db=self.root/"sqlite"/"v4-shadow.sqlite3"
        with closing(sqlite3.connect(self.db)) as conn:
            _init(conn)
            for i in range(25):
                rid=f"v4-guarded-{i:03}"
                raw=(json.dumps({"instance":f"market:fixture:{i:03}",
                                 "status":"WATCH","reason":"TEST"})+"\n").encode()
                folder=self.root/"runs"/str(i)
                folder.mkdir()
                (folder/"all_proofs.jsonl").write_bytes(raw)
                (folder/"deep_shadow.json").write_text(
                    json.dumps({"run_id":rid}),encoding="utf-8")
                conn.execute(
                    "INSERT INTO scan_runs VALUES (?,?,?,?,?,?)",
                    (rid,"SHADOW_VERIFIED_OFFLINE",1,
                     hashlib.sha256(raw).hexdigest(),"{}",
                     f"2026-10-{i+1:02}T00:00:00+00:00"))
                conn.execute("INSERT INTO proof_versions VALUES (?,?,?,?,?)",
                             (rid,f"market:fixture:{i:03}","WATCH","TEST",
                              raw.decode().strip()))
            conn.commit()
        self.original_bytes=self.db.stat().st_size
        self.external=self.sandbox/"remote-backup.sqlite3"
        shutil.copyfile(self.db,self.external)
        old=ledger_runs(self.root)[-1]
        with patch("v4.proof_cold_archive.MIN_FREE_GIB",0):
            archive_one(self.root,old,source_index(self.root)[old["run_id"]])
        with patch("v4.hot_ledger_stage.MIN_FREE_GIB",0):
            result=stage(self.root,keep_runs=24)
        self.candidate=Path(result["candidate_db"])

    @staticmethod
    def _n(path,sql):
        with closing(sqlite3.connect(path)) as db:
            return db.execute(sql).fetchone()[0]

    def _activate(self):
        with patch("v4.hot_cutover._check_tasks_disabled"), \
             patch("v4.hot_cutover.GIB",1):
            return activate(self.root,candidate=self.candidate,
                            external_backup=self.external,
                            acknowledgement=ACK)

    def test_readonly_inspection_no_database_mutation(self):
        report=inspect(self.root,candidate=self.candidate)
        self.assertEqual(report["status"],"READ_ONLY_CUTOVER_INSPECTION")
        self.assertFalse(report["cutover_performed"])
        self.assertFalse(report["live_database_modified"])
        self.assertEqual(self._n(self.db,
                         "SELECT COUNT(*) FROM proof_versions"),25)

    def test_cutover_keeps_original_and_external_backup(self):
        result=self._activate()
        self.assertEqual(result["status"],
                         "ACTIVATED_NEEDS_OPERATOR_REENABLE_TASKS")
        self.assertTrue(Path(result["original_rollback_file"]).is_file())
        self.assertEqual(self._n(self.db,
                         "SELECT COUNT(*) FROM proof_versions"),24)
        self.assertEqual(self._n(self.db,
                         "SELECT active FROM v4_hot_policy"),1)
        self.assertEqual(self._n(Path(result["original_rollback_file"]),
                         "SELECT COUNT(*) FROM proof_versions"),25)
        self.assertEqual(self._n(self.external,
                         "SELECT COUNT(*) FROM proof_versions"),25)
        self.assertEqual(self._n(self.candidate,
                         "SELECT active FROM v4_hot_policy"),0)

    def test_wrong_ack_does_not_mutate(self):
        with self.assertRaisesRegex(RuntimeError,"ACK_REQUIRED"):
            self._unsafe_ack()
        self.assertEqual(self._n(self.db,
                         "SELECT COUNT(*) FROM proof_versions"),25)

    def _unsafe_ack(self):
        with patch("v4.hot_cutover._check_tasks_disabled"):
            activate(self.root,candidate=self.candidate,
                     external_backup=self.external,
                     acknowledgement="")

    def test_outdated_external_backup_rejected_without_swap(self):
        with closing(sqlite3.connect(self.external)) as db:
            db.execute(
                "DELETE FROM proof_versions WHERE run_id=?",
                ("v4-guarded-000",))
            db.commit()
        with self.assertRaisesRegex(RuntimeError,
                                    "BACKUP_PROOF_COUNT_INCONSISTENT"):
            self._activate()
        self.assertEqual(self._n(self.db,
                         "SELECT COUNT(*) FROM proof_versions"),25)

    def test_stale_candidate_rejected_without_swap(self):
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("INSERT INTO scan_runs VALUES (?,?,?,?,?,?)",
                       ("v4-post-stage","SHADOW_VERIFIED_OFFLINE",1,
                        "new-hash","{}","2026-10-26T00:00:00Z"))
            db.commit()
        with self.assertRaisesRegex(RuntimeError,
                                    "STAGED_CANDIDATE_NOT_READY"):
            self._activate()
        self.assertEqual(self._n(self.db,
                         "SELECT COUNT(*) FROM proof_versions"),25)

    def test_failed_second_rename_rolls_back_immediately(self):
        original=os.replace
        moves=[]
        def flaky(source,dest):
            moves.append((str(source),str(dest)))
            if len(moves)==2:
                raise PermissionError("simulated locked candidate")
            return original(source,dest)
        with patch("v4.hot_cutover._check_tasks_disabled"), \
             patch("v4.hot_cutover.GIB",1), \
             patch("v4.hot_cutover.os.replace",side_effect=flaky):
            with self.assertRaisesRegex(PermissionError,"locked"):
                activate(self.root,candidate=self.candidate,
                         external_backup=self.external,acknowledgement=ACK)
        self.assertGreaterEqual(len(moves),3)
        self.assertTrue(self.db.exists())
        self.assertEqual(self._n(self.db,
                         "SELECT COUNT(*) FROM proof_versions"),25)

    def test_task_enabled_flag_requires_settings_not_trigger(self):
        xml=b"""<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
          <Triggers><TimeTrigger><Enabled>false</Enabled></TimeTrigger></Triggers>
          <Settings><Enabled>true</Enabled></Settings></Task>"""
        with patch("v4.hot_cutover.subprocess.run") as fake:
            fake.return_value.returncode=0
            fake.return_value.stdout=xml
            self.assertFalse(_task_disabled("EVE-V4-Shadow"))
            fake.return_value.stdout=xml.replace(
                b"<Settings><Enabled>true",b"<Settings><Enabled>false")
            self.assertTrue(_task_disabled("EVE-V4-Shadow"))


if __name__=="__main__":
    unittest.main()
