# V4 controlled SQLite hot/cold cutover — Windows-only runbook

**Status as of 2026-10-25: tooling committed, NOT executed on user's Windows host.**
The earlier Windows **41 tests OK** covers cold archival / staging / retention,
but does not establish that the newly introduced cutover script passes tests.
Until confirmed, do not use `--apply`. Production SQLite remains unmodified.

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
both tasks with `Enable-ScheduledTask` and confirm scheduler status
and a fresh formal opportunity cycle. Observe real `vacuum_pages_reclaimed`
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
