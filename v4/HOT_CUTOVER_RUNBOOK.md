# V4 controlled SQLite hot/cold cutover — Windows-only runbook

**Status as of 2026-10-26: Windows cutover fixture tests 12/12 OK,
actual production cutover NOT performed.** The former candidate is rejected
with `STAGE_MANIFEST_INVALID`, and no independent current external backup
has been verified. Do not run `hot_cutover --apply` yet.

## Operator decision: retire duplicate standalone market opportunity lane

On 2026-10-25, the operator chose to **stop scanning and sending**
the `EVE V4 市场机会` notification while continuing the
`V4捡漏待核` combined market-and-contract research notification.

Verified in source:
- `v4/opportunity_push.py` formats subject
  `EVE V4 市场机会 ...`; the related Windows scheduled task is
  `EVE-V4-Opportunity-Push`. **Keep DISABLED indefinitely.**
- `v4/unified_review.py` formats subject
  `V4捡漏待核 ...`; `EVE-V4-Shadow` generates/sends this
  market+contract review. **Keep ENABLED** except for a brief,
  explicitly coordinated database maintenance interval.
- Do not alter EVE SSO, installed code, scanned evidence, Gmail
  configuration, character recipients or the old market-opportunity
  state. Disabling the scheduled task is reversible and does not
  erase historical data.
- These are separate local Windows tasks, not active ChatGPT cloud
  task automations. GitHub repository changes alone cannot disable
  an already-installed task on the user's Windows host.
- Task disabling is not proof any currently running invocation has
  finished; an in-flight scan or send can complete.
- During future cutovers, leave `EVE-V4-Opportunity-Push` disabled
  both before and after the window. Only re-enable
  `EVE-V4-Shadow` once verified healthy. Do not unconditionally
  enable both tasks as the earlier generic runbook instructed.

**One-time operator-side action:**

```powershell
Disable-ScheduledTask -TaskName "EVE-V4-Opportunity-Push" -ErrorAction Stop
Get-ScheduledTask -TaskName "EVE-V4-Opportunity-Push","EVE-V4-Shadow" |
    Select-Object TaskName,State
```

## Important process concurrency fact

Both installed scheduled tasks use **the same**
`$HOME\EVE-V4-Data\v4-local-shadow.lock`:
- `EVE-V4-Shadow`: public/private research shadow scan, large SQLite writes.
- `EVE-V4-Opportunity-Push`: **formal opportunity notifications**, independent
  fresh-ESI scans; it shares the scanner lock even though it does NOT rely on
  historical SQLite proof rows.

**For a database switchover, temporarily disable BOTH tasks.** Otherwise
the push task may fail with `ANOTHER_V4_LOCAL_SCAN_RUNNING`, or a shadow job
may write during cutover. This is a limited, intentional notification pause;
you MUST re-enable the retained **Shadow** task after activation or if any step is blocked; leave **Opportunity-Push** disabled by operator decision.
Do NOT force-stop a running scan while it is committing evidence;
wait for it to complete. Merely disabling a scheduled task does not
necessarily stop its already-running invocation.

## Windows cutover-fixture repair (2026-10-25)

The operator ran the initial 8 cutover tests. Five were blocked:
- Several fixtures unexpectedly left SQLite WAL/SHM sidecars after
  `v4.local_store._init` (which intentionally enables WAL); the
  cutover guard correctly rejected them with
  `SQLITE_JOURNAL_PRESENT_CLOSE_ALL_V4_READERS`. **Never weaken this
  production guard.** The isolated fixtures now checkpoint, switch to
  DELETE journal mode and assert the sidecars disappear before testing
  valid cutovers. A separate test deliberately adds a WAL marker and
  verifies that activation is refused without changing the source DB.
- The stale-candidate test had inserted a `scan_runs` row without a
  corresponding proof row; the separate full-history integrity guard
  correctly rejected this input before the stale-candidate check.
  The fixture now adds the proof and refreshes its simulated external
  backup, so a stale candidate can be tested independently.
- The external-volume test reached the sidecar guard before its
  volume guard and is now reachable with a clean fixture.

This is a historical note: the interim suite had 9 tests;
the current 12-test suite **passed on the operator's Windows host**.
Passing fixture tests alone does not permit a production cutover.

## Windows read-only inspection fix (2026-10-25)

The user verified **9/9 cutover unit tests OK**, while
`python -m v4.hot_cutover` (read-only) reported:
- `STAGE_MANIFEST_INVALID` for the original
  `v4-shadow-hot-20261025T021742Z-4616.sqlite3`. This file predates
  the new `incremental_auto_vacuum`, inactive `v4_hot_policy` and
  historical cold-index changes. This is a **valid fail-closed outcome**;
  rebuild a NEW stage only after a maintenance window is arranged.
- `SCHEDULED_TASK_XML_INVALID` for both Windows scheduled tasks.
  A real-world Windows schtasks.exe quirk is a UTF-16 XML declaration
  emitted over non-UTF16 console/UTF-8 data bytes. The original parser
  used `ET.fromstring(stdout_bytes)`, which fails. The updated parser
  first tries direct bytes, then strict decoded Unicode paths
  (UTF-8/UTF-16/Windows console encodings), validates the root is a
  Task, and always reads the overall `Settings.Enabled` node.
  Unreadable/unrecognized XML **still blocks a production cutover**.
  Added 3 tests: UTF-16-declared UTF-8 bytes, GBK Chinese XML,
  malformed XML/unknown Enabled. New expected test count **12**.
  This fix subsequently passed in the user's **12/12 Windows test run**.

No task or SQLite state has been changed as a result of these
read-only diagnostics. In particular, the user-requested disabled
`EVE-V4-Opportunity-Push` task must remain disabled. Do not run
`hot_cutover --apply` based on a read-only inspection.

## Gate A — code pull, tests, strictly read-only inspection

```powershell
Set-Location "$HOME\EVE-V4-Code"
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }
$py = '.\.venv\Scripts\python.exe'
& $py -m unittest -v v4.tests.test_hot_cutover
if ($LASTEXITCODE -ne 0) { throw 'Cutover tests failed; leave production alone' }
& $py -m v4.hot_cutover
```

The last command is **read-only**. It reports the candidate's
freshness/policy/cold-index state and whether the tasks appear enabled.
Before cutover, `status: READ_ONLY_CUTOVER_INSPECTION` is expected.
An old 7.782 GiB candidate created before policy/index changes is obsolete
and MUST NOT be activated. A newly staged candidate can become stale
whenever another hourly shadow scan finishes.

## D-drive verified backup helper (2026-10-26)

The latest real Windows storage inventory was: C: free **208.1 GiB**,
D: free **868.2 GiB**, project root **155.199 GiB**. The hot policy
still reports `NOT_CONFIGURED`; the old candidate is NOT_READY.

The new `python -m v4.external_backup --backup-dir D:\\V4-Safe-Backup`
command is **READ-ONLY** and reports backup capacity. Its opt-in
`--create` form demands BOTH `EVE-V4-Shadow` and
`EVE-V4-Opportunity-Push` Disabled and the shared process lock available;
the online backup reads SQLite WAL safely, only writes a new full backup
under the requested other volume and checks SQLite `integrity_check`,
scan-run metadata and proof counts **before publishing** it. It will
never overwrite a previous backup or delete evidence. The first Windows test run of the backup suite failed 5/6 fixture tests
because its simulated destination shared the source temp directory volume;
the **real cross-volume production guard was correctly blocking**.
Only the isolated test fixtures now mock the cross-volume check; a new
independent Windows unit test explicitly proves that same-volume backup
is rejected by the real check. Updated suite now contains **7 tests**.
The updated seven-test suite has NOT yet been verified on Windows.
Run `python -m unittest -v v4.tests.test_external_backup` before creating
an actual backup.

Example two-stage process, STOP AFTER backup+preflight and report the
candidate/backup paths, DO NOT automatically `--apply`:

```powershell
# A: while V4-Shadow is ENABLED, read-only
$py = '.\.venv\Scripts\python.exe'
& $py -m unittest -v v4.tests.test_external_backup
if ($LASTEXITCODE -ne 0) { throw 'External-backup tests FAILED' }
& $py -m v4.external_backup --backup-dir 'D:\V4-Safe-Backup'

# B: ADMINISTRATOR POWERSHELL, controlled maintenance
Disable-ScheduledTask -TaskName 'EVE-V4-Shadow' -ErrorAction Stop
$state = Get-ScheduledTask -TaskName 'EVE-V4-Shadow','EVE-V4-Opportunity-Push'
$state | Select-Object TaskName,State
if (@($state | Where-Object State -ne 'Disabled').Count -ne 0) {
    throw 'Both jobs must be Disabled'
}
# Disabling does NOT interrupt already-running scans.
# Check Windows process list; wait for jobs to FINISH normally.
# NEVER delete -wal or -shm by hand.
& $py -m v4.proof_cold_archive --apply --all
if ($LASTEXITCODE -ne 0) { throw 'Cold archive incomplete' }
& $py -m v4.hot_ledger_stage --stage
if ($LASTEXITCODE -ne 0) { throw 'Stage failed' }
& $py -m v4.hot_cutover_preflight --verify-hash
if ($LASTEXITCODE -ne 0) { throw 'Candidate not current' }
& $py -m v4.external_backup --backup-dir 'D:\V4-Safe-Backup' --create
if ($LASTEXITCODE -ne 0) { throw 'External full backup failed' }
# STOP and examine output; do not --apply in this step.
```

If Stage or backup is blocked by a sidecar, preserve the DB and
sidecars, inspect active SQLite handles, and perform a controlled
checkpoint only after all writers/readers are closed. Do not override
fail-closed checks. Stop `EVE-V4-Shadow` as briefly as practical,
and on a preparation failure with the live DB still intact, re-enable
**only** `EVE-V4-Shadow` after checking nothing has been renamed.

D: is a distinct logical volume. If C: and D: share one physical
disk, D: alone does not protect against disk failure; also make an
off-machine verified copy before considering any rollback deletion.

## 2026-10-26: online backup WAL/SHM mismatch fixed (code only)

The user's second real preparation produced a NEW 7.802 GiB hot candidate
`v4-shadow-hot-20261026T132337Z-27552.sqlite3` with 279 scan run records,
72 hot and 207 cold runs; SHA preflight returned
`CANDIDATE_READY_FOR_CONTROLLED_MAINTENANCE`. The external backup
`--create` was BLOCKED with
`SQLITE_JOURNAL_PRESENT_CLOSE_ALL_V4_READERS` because the live production
DB still had at least one SQLite journal/WAL sidecar; the maintenance
PowerShell finally block restored Shadow task to Ready, with standalone
Opportunity-Push remaining Disabled. **No production swap or D backup
occurred.**

SQLite `Connection.backup()` is WAL-aware and copies committed WAL
transactions. Its earlier sidecar precheck was appropriate for destructive
live DB rename, **not** for a read-only source online full backup. The
patched `v4.external_backup` now performs the same gated no-writer,
current-ledger and integrity verifications, while tolerating the SOURCE
`-wal`/`-shm` files and NEVER manually deleting or renaming them.
The DESTINATION is made self-contained by its own SQLite
`wal_checkpoint(TRUNCATE)` and `journal_mode=DELETE`, closed,
checked for sidecars, reopened with `immutable=1` and its integrity
and proof count independently checked BEFORE publishing. The
`v4.hot_cutover` strict source/candidate sidecar guard is UNCHANGED.

The new WAL-aware backup regression uses a real committed WAL transaction
and separately asserts that the unchanged cutover sidecar guard still
rejects such a database. **Patch/tests not yet Windows-verified.**

**Important: a successful online backup does NOT, by itself, permit
hot cutover.** Before promoting a candidate in a controlled maintenance
window, the live database must be cleanly checkpointed by SQLite itself
and left in a fully self-contained state, with no active V4 writer or
reader, then source, external backup and hot candidate preflight must
all be revalidated. Never delete `-wal` or `-shm` by hand. Resume ONLY
`EVE-V4-Shadow` on a blocked preparation. A subsequent Shadow scan
will make the staged candidate/backup stale, so regenerate them after
the final scanner pause.

## Gate B — operator maintenance window (NOT automatic)

1. Check no backup integrity check or shadow/push job currently running.
2. Explicitly disable BOTH tasks (preserve trigger/settings):
   `Disable-ScheduledTask -TaskName 'EVE-V4-Shadow'` and
   `Disable-ScheduledTask -TaskName 'EVE-V4-Opportunity-Push'`.
   Confirm `Get-ScheduledTask ... | Select TaskName,State` reports Disabled;
   inspect live processes before acting, and allow already-running tasks
   to finish normally.
3. If any process is still doing a scan/backup/push, **do not proceed**.
4. Finish any newly expired archives:
   `python -m v4.proof_cold_archive --apply --all`
   (this never modifies live SQLite). Confirm `failed: []` and
   `status: ARCHIVE_RUN_COMPLETE`.
5. Stage a new up-to-date candidate:
   `python -m v4.hot_ledger_stage --stage`.
   A candidate should have
   `v4_hot_policy(active=0,keep_runs=72)`,
   `v4_cold_proofs` and `PRAGMA auto_vacuum=2`.
6. Run `python -m v4.hot_cutover_preflight --verify-hash`
   and require `CANDIDATE_READY_FOR_CONTROLLED_MAINTENANCE`.
7. Create an independent *current* full SQLite backup on a separate,
   preferably unplugged-after-copy disk/computer. Do NOT copy the live
   SQLite file while WAL writers are active; use SQLite's online backup API
   or an integrity-checked completed daily backup whose run set is identical
   to the new candidate. The cutover program verifies its
   `PRAGMA integrity_check`, historical run metadata and proof row count,
   rejects a stale/truncated backup, and requires a different Windows
   volume from the active database. **Different volume is only a technical
   check, not proof it is physically off-machine**; operator must ensure
   proper disaster recovery.

## Gate C — controlled promotion (ONLY after Gate A/B and explicit approval)

```powershell
# EXAMPLE ONLY. Replace paths with values confirmed by Gate B.
# & $py -m v4.hot_cutover --apply `
#   --candidate 'C:\Users\mike\EVE-V4-Data\hot-stage\<NEW>.sqlite3' `
#   --external-backup 'D:\V4-safe-backup\<CURRENT>.sqlite3' `
#   --ack I_ACCEPT_V4_HOT_CUTOVER
```

The cutover script independently verifies:
- both Windows tasks are disabled via `schtasks /Query /XML`,
  **Settings.Enabled=false**, ignoring disabled triggers;
- the V4 scanner/push exclusive process lock is free;
- no WAL/SHM/journal sidecars for the source/staged candidate;
- current external full backup on a different Windows volume;
- live historical ledger is still complete and the newest candidate
  matches its CURRENT full run set and sealed SHA256;
- sufficient free space for an activated candidate copy.

It copies the candidate to a new *temporary* SQLite DB, enables the
72-run policy marker there (not in the immutable archived candidate),
and verifies the activated copy. It moves the original DB without
deleting it into `hot-cutover-rollback/` and promotes the activated
copy to `sqlite/v4-shadow.sqlite3`. It rechecks integrity/policy and
tries immediate rollback on any promotion failure. Unexpected host
shutdown between two rename operations requires manual recovery.
**Never delete/copy/rename WAL or SHM files by hand.**

After success: first run a small read-only audit and verify the latest
`HOT_PROOF_RETENTION` record after resumed shadow scan; re-enable
**ONLY `EVE-V4-Shadow`** with `Enable-ScheduledTask` and confirm
the combined review mail resumes. `EVE-V4-Opportunity-Push` MUST remain
Disabled by operator decision. Observe real `vacuum_pages_reclaimed`
and `vacuum_incomplete` before claiming long-run size is bounded.

## Disk consumption caveat

Successful activation makes the LIVE SQLite about 8 GiB rather than
23+ GiB, but **total disk free space does not immediately improve**:
the old 23+ GiB database is preserved under `hot-cutover-rollback/`,
the staged candidate is still present, and there may be an activated-copy
workspace. Only after an independent restore has been tested, production
has run and pushed correctly for a monitored period, and an off-machine
copy of the old data is secure should deleting redundant local rollback
copies be considered. That is a SEPARATE approval, never automated here.

## Rollback safety

During the paused maintenance window, if promotion fails, the tool
automatically attempts to restore the original DB and keeps a failed
activated candidate as evidence. If the host powers off mid-rename,
inspect `hot-cutover-rollback/` and `sqlite/` before starting tasks.

**Once production scans run against the new DB, do not simply restore
the original SQLite from before cutover**: any new completed scans must
be preserved and replayed from their `runs/` artifacts before rollback.
A full post-activation recovery procedure and actual independent
restore drill remain prerequisites to declaring migration complete.

### Abort / task re-enable

If any Gate B/C command fails without altering the active DB,
after checking the source is still intact and no partial cutover rename
occurred, re-enable only the retained Shadow task:
`Enable-ScheduledTask -TaskName 'EVE-V4-Shadow'`
Do NOT re-enable `EVE-V4-Opportunity-Push`..
Inspect `Get-ScheduledTask` and per-task logs.

At no point does pulling this code automatically activate or prune
the user's existing live 23+ GiB SQLite database.
