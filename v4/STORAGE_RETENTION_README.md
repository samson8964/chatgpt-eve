# EVE V4 storage controls — staged deployment

This change reduces local backup accumulation without altering V4 market
evaluation, EVE SSO, Cloudflare Workers, Gmail, game mail, scheduled job
definitions, SQLite historical rows, or historical market and contract captures.

## Why

Observed on 2026-10-24 from the operator's Windows host:
- backups: 86.46 GiB in 12 files
- hot SQLite: 23.05 GiB
- runs: 21.73 GiB
- esi-parallel-validation: 4.65 GiB

Old daily copies of a growing SQLite database explain most space usage.
The three latest observed backups are 20.44, 17.48, 14.62 GiB.
Keeping the last 3 will release about **33.92 GiB** if file sizes have
not changed. This is an estimate, not a deletion performed by this commit.

## Upgrade and verify (PowerShell)

    $repo = Join-Path $HOME 'EVE-V4-Code'
    $expected = 'prep/v4-windows-local-migration-20261013'
    $current = (git -C $repo branch --show-current).Trim()
    if ($current -ne $expected) { throw "Wrong branch: $current" }
    git -C $repo pull --ff-only
    if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }
    Set-Location $repo
    & .\.venv\Scripts\python.exe -m unittest v4.tests.test_storage_retention v4.tests.test_storage_audit v4.tests.test_local_backup_atomic v4.tests.test_local_service v4.tests.test_local_store
    if ($LASTEXITCODE -ne 0) { throw 'Do not apply: tests failed' }

Preview which old backups would be removed (NO deletes, NO SQLite writes):

    & .\.venv\Scripts\python.exe -m v4.storage_retention

One-time verified backup rotation (deletes ONLY the older, exactly named
v4-shadow-*.sqlite3 files, provided the 3 newest copies are from 3
different UTC dates and each passes SQLite quick_check and schema checks):

    & .\.venv\Scripts\python.exe -m v4.storage_retention --apply
    if ($LASTEXITCODE -ne 0) { throw 'Backup rotation blocked' }

New daily backup files are now first generated as *.sqlite3.part, promoted
to *.sqlite3 ONLY after full SQLite integrity_check + required table checks.
A failed creation does not leave a falsely valid current backup file.

Existing daily backups created by EVE-V4-Shadow now trigger the SAME
safety-checked rotation automatically AFTER backup creation and full
integrity_check succeeds. A failed retention check leaves all backups
untouched, records backup_retention.status='BLOCKED', and does NOT
interrupt an otherwise completed scan or its mail channels. It uses a
separate v4-backup-retention.lock so the hourly opportunity scanner is
not delayed by SQLite verification. This is enabled by pulling the new
code; no scheduled task modification is needed.

The rotation changes only local historical backups. It does not delete
the active sqlite/v4-shadow.sqlite3 or its journal files. Backups are
verified as SQLite databases; the quick_check for old retained copies
is not a substitute for an independently tested restore.

## Inspect the hot database (read only)

    & .\.venv\Scripts\python.exe -m v4.storage_audit
    & .\.venv\Scripts\python.exe -m v4.storage_audit --deep

The first command reports file totals and SQLite allocated/free pages.
The --deep command reads SQLite B-tree page statistics and row counts;
it can take time on a 23 GiB database but NEVER changes data. Use it
before choosing a reversible proof-version archive and hot-retention
window.

## Audit results and phase-2 decision (2026-10-24)

Operator supplied a live read-only audit after the manual rotation:

- sqlite/v4-shadow.sqlite3: 23.162 GiB (plus tiny WAL/SHM files)
- scan_runs: 235
- proof_versions: 13,788,412 rows (~58,674 proof rows per completed run)
- SQLite freelist pages: 0 GiB. This is NOT a reliable upper bound
  on VACUUM savings; VACUUM can compact partly empty pages.
- dbstat virtual table: unavailable in Windows Python. The enhanced audit
  now samples 128 rowids to estimate stored proof_json byte lengths
  without the dbstat extension.
- backup directory: 63.772 GiB, 5 files in the audit immediately after
  a manual rotation deleted 9 older named snapshots (33.92 GiB freed).
  Do not infer which 2 extra files are present: enhanced audit prints
  every backup filename and size; identify them before further deletion.

Because proof_versions is keyed by (run_id, instance), the offline shadow
research ledger copies a full set of proofs every run even for unchanged
instances. The production opportunity push has a separate code path;
however, retained proofs are valuable for audit, evidence and reproducibility.
No retroactive hot SQLite purge has been authorized or performed.

Proposed future lossless cold archive (NOT deployed):

1. Select old completed run IDs outside a conservative hot window.
2. Verify each run's original all_proofs.jsonl stream against persisted
   proof_sha256 and proof_count, cross-check corresponding manifest and
   scan_runs metadata.
3. Write immutable per-run compressed cold archive(s) with SHA256 checksums,
   independent manifest, and a checked round-trip restore routine.
4. Verify at least one independent backup/off-machine copy before any
   source/ledger compaction.
5. Build a new smaller hot SQLite offline from preserved recent runs.
   Verify count, SHA256, historical archive lookup, and mail isolation;
   replace production only in a planned maintenance window while scheduled
   tasks are stopped, with a tested rollback. Do NOT perform DELETE/VACUUM
   on the live 23+ GiB database while hourly jobs are running.
6. Retain opportunities, audit manifests and indexed history separately;
   never treat shadow proofs as confirmed trade execution.

Command to inspect this phase (read-only, after git pull):

    & .\\.venv\\Scripts\\python.exe -m v4.storage_audit --deep

Examine backup_inventory.largest_files / unrecognized_files and
hot_sqlite.proof_json_sample. DBSTAT_UNAVAILABLE is expected on some
SQLite builds and is not database corruption.

## Deferred until the main DB archive is restore-tested

- proof_versions is append-only by (run_id, instance); old proofs can
  duplicate repeated observations across scans.
- Historical proof rows SHOULD be exported with checked manifests and
  a verified restore path before any pruning, deduplication or VACUUM.
- runs/ and esi-parallel-validation/ contain source provenance and
  audit artifacts; they are NOT deleted by this change.
- Off-machine backups are still required. This deployment does not
  invent a cloud destination or assume local backups are disaster-proof.
- NEVER manually erase the hot database or its -wal/-shm files.

## Rollback

To stop automatic local rotation, revert the relevant Git commits or
restore the prior local_service.py. Previously deleted older local
backup files cannot be reconstructed by git; keep a separate off-machine
restore point. Active SQLite and proof tables remain unchanged.

## Verification after next automatic daily backup

Inspect the newest RESULT in data-root/logs/shadow-task.log. If an
automatic backup was due, it should include:

    backup: COMPLETE
    backup_retention: {status: ROTATED|NOT_NEEDED|BLOCKED_RECENT_DAYS_NOT_DISTINCT|BLOCKED, ...}

Only ROTATED means space was released. Check backup folder contains three
verified recent files, and check the next opportunity email still runs.
