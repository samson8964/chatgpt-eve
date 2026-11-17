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
from types import SimpleNamespace
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
            # _init intentionally uses WAL for real scans. The cutover
            # requires a fully closed/checkpointed source with NO sidecars.
            # Model that *clean maintenance state* explicitly in fixtures
            # instead of bypassing the production sidecar safety guard.
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            mode=conn.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
            self.assertEqual(mode.lower(),"delete")
        self.assertFalse(self.db.with_name(self.db.name+"-wal").exists())
        self.assertFalse(self.db.with_name(self.db.name+"-shm").exists())
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
        # The compact fixture keeps its simulated "external" backup on the
        # same temporary volume. Bypass ONLY the production Windows volume
        # check for these algorithm/rollback tests; separately assert that
        # the real Windows different-volume guard remains fail-closed.
        with patch("v4.hot_cutover._check_tasks_disabled"), \
             patch("v4.hot_cutover.platform",
                   SimpleNamespace(system=lambda: "Linux")), \
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

    def test_windows_requires_separate_backup_volume(self):
        # This is a real, essential production safety check and must not
        # be bypassed outside of the isolated rollback unit fixtures.
        with patch("v4.hot_cutover._check_tasks_disabled"), \
             patch("v4.hot_cutover.platform",
                   SimpleNamespace(system=lambda: "Windows")), \
             patch("v4.hot_cutover.GIB",1):
            with self.assertRaisesRegex(
                    RuntimeError,"EXTERNAL_BACKUP_MUST_BE_ON_OTHER_VOLUME"):
                activate(self.root,candidate=self.candidate,
                         external_backup=self.external,acknowledgement=ACK)
        self.assertEqual(self._n(
            self.db,"SELECT COUNT(*) FROM proof_versions"),25)

    def test_stale_candidate_rejected_without_swap(self):
        # A real completed run has *both* metadata and its full proof set.
        # The independent backup is updated to CURRENT, allowing the test
        # to reach the intended stale-candidate safety check.
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("INSERT INTO scan_runs VALUES (?,?,?,?,?,?)",
                       ("v4-post-stage","SHADOW_VERIFIED_OFFLINE",1,
                        "new-hash","{}","2026-10-26T00:00:00Z"))
            db.execute(
                "INSERT INTO proof_versions VALUES (?,?,?,?,?)",
                ("v4-post-stage","market:new:001","WATCH","TEST",
                 '{"instance":"market:new:001"}'))
            db.commit()
        shutil.copyfile(self.db,self.external)
        with self.assertRaisesRegex(RuntimeError,
                                    "STAGED_CANDIDATE_NOT_READY"):
            self._activate()
        self.assertEqual(self._n(self.db,
                         "SELECT COUNT(*) FROM proof_versions"),26)

    def test_failed_second_rename_rolls_back_immediately(self):
        original=os.replace
        moves=[]
        def flaky(source,dest):
            moves.append((str(source),str(dest)))
            if len(moves)==2:
                raise PermissionError("simulated locked candidate")
            return original(source,dest)
        with patch("v4.hot_cutover._check_tasks_disabled"), \
             patch("v4.hot_cutover.platform",
                   SimpleNamespace(system=lambda: "Linux")), \
             patch("v4.hot_cutover.GIB",1), \
             patch("v4.hot_cutover.os.replace",side_effect=flaky):
            with self.assertRaisesRegex(PermissionError,"locked"):
                activate(self.root,candidate=self.candidate,
                         external_backup=self.external,acknowledgement=ACK)
        self.assertGreaterEqual(len(moves),3)
        self.assertTrue(self.db.exists())
        self.assertEqual(self._n(self.db,
                         "SELECT COUNT(*) FROM proof_versions"),25)

    def test_real_live_sidecar_is_rejected_without_mutating(self):
        # Even an empty WAL marker blocks promotion. It must never be
        # silently discarded because SQLite may require its contents.
        wal=self.db.with_name(self.db.name+"-wal")
        wal.write_bytes(b"uncheckpointed-fixture")
        try:
            with self.assertRaisesRegex(
                    RuntimeError,"SQLITE_JOURNAL_PRESENT_CLOSE_ALL_V4_READERS"):
                self._activate()
            self.assertEqual(self._n(
                self.db,"SELECT COUNT(*) FROM proof_versions"),25)
        finally:
            wal.unlink(missing_ok=True)

    def test_windows_utf16_declaration_with_utf8_bytes(self):
        # Observed schtasks.exe /Query /XML behavior: declaration says
        # UTF-16 while the actual stdout has UTF-8-compatible bytes.
        xml=('<?xml version="1.0" encoding="UTF-16"?>\r\n'
             '<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
             '<Settings><Enabled>false</Enabled></Settings></Task>')
        with patch("v4.hot_cutover.subprocess.run") as fake:
            fake.return_value.returncode=0
            fake.return_value.stdout=xml.encode("utf-8")
            self.assertTrue(_task_disabled("EVE-V4-Opportunity-Push"))
            fake.return_value.stdout=xml.replace(
                "<Enabled>false", "<Enabled>true").encode("utf-8")
            self.assertFalse(_task_disabled("EVE-V4-Shadow"))

    def test_chinese_oem_codepage_xml_and_disabled_setting(self):
        xml=('<?xml version="1.0" encoding="UTF-16"?>'
             '<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
             '<RegistrationInfo><Description>本地捡漏检查</Description></RegistrationInfo>'
             '<Settings><Enabled>false</Enabled></Settings></Task>')
        with patch("v4.hot_cutover.subprocess.run") as fake:
            fake.return_value.returncode=0
            fake.return_value.stdout=xml.encode("cp936")
            self.assertTrue(_task_disabled("EVE-V4-Opportunity-Push"))

    def test_unreadable_task_xml_remains_fail_closed(self):
        with patch("v4.hot_cutover.subprocess.run") as fake:
            fake.return_value.returncode=0
            fake.return_value.stdout=b'NOT AN XML DOCUMENT'
            with self.assertRaisesRegex(
                    RuntimeError,"SCHEDULED_TASK_XML_INVALID"):
                _task_disabled("EVE-V4-Shadow")
            fake.return_value.stdout=(
                b'<Task><Settings></Settings></Task>')
            self.assertFalse(_task_disabled("EVE-V4-Shadow"))

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
