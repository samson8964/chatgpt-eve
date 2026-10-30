# V4 capacity governor — deployment / safety notes (2026-10-26)

## Current reality

The local Windows scheduled task `EVE-V4-Shadow` remains ENABLED (Ready),
and `EVE-V4-Opportunity-Push` was disabled by the operator. Do not reenable
`EVE-V4-Opportunity-Push` under any maintenance path.

The old 23+ GiB `sqlite/v4-shadow.sqlite3` has not been replaced.
The 2026-10-25 hot-stage candidate is old and rejected by
`STAGE_MANIFEST_INVALID`. `v4.hot_cutover` passed 12 Windows fixture
tests but **actual cutover has not occurred**. Consequently the automatic
72-run hot proof pruning is still inactive on the production DB.

## What this patch does automatically after git pull

- Read-only, symlink/junction-aware per-directory capacity inventory for
  `runs`, `sqlite`, `backups`, `cold-proof-archives`,
  `esi-parallel-validation`, `hot-stage`, rollback and logs.
- Retain up to 720 hourly usage samples in
  `logs/storage-capacity-history.json`. This is a tiny telemetry file
  written atomically, not a backup and not a proof artifact.
- Calculate recent free-space rate (6–30h observation window) and
  warn if free space falls below 40 GiB, or the observed rate would
  reach the 20 GiB scanner-stop line within seven days.
- If free space falls below 20 GiB, the scanner is already blocked by
  `storage_check`; `local_service.main` now **never sends an old
  opportunity mail** when no current scan happened. Returns code 4.
- New `v4.storage_alert` sends one distinct storage warning email
  per UTC day and severity (WARNING or STOP), using the **existing**
  research Gmail configuration/Windows vault. The email is not
  labeled as a trade, and has a separate `logs/storage-alert-receipts`
  receipt. If research Gmail is disabled, no outbound mail is sent.
  Any alert exception is logged and does not suppress normal scan mail.
- After each completed scan, after the existing research delivery and
  hot retention hook, append capacity health to `logs/shadow-task.log`
  as `STORAGE_GOVERNOR`. Skipped stale/low-disk cycles also produce
  a capacity check. This does not add a scheduled job.

## Safety limits / what is NOT yet enabled

- `storage_governor` **NEVER deletes raw snapshots, contract artifacts,
  cold proofs, mail receipts, live SQL rows, rollback files or backups**.
- It does not `VACUUM`, switch databases, restart tasks, or run
  Cloudflare workers.
- `v4.hot_retention` remains fail-closed until the hot-policy DB is
  promoted under the independent-backup cutover runbook.
- The existing `storage_retention.rotate_backups` may already delete
  redundant **old verified local SQLite backup files** after a new
  verified backup and multiple distinct recent restore days. The new
  governor does not change this existing behavior.
- Entire-project disk usage is **not yet automatically bounded**:
  historical raw source archives, cold proof archives, old hot-stage
  candidates and rollback retention still require an approved lifecycle
  policy and an external/off-machine backup destination.
- Do not set a blind deletion-by-age policy on irreplaceable historical
  raw snapshots. Remote/off-machine replication with checksum and tested
  restore is a prerequisite for moving or purging local copies.

## Operator commands (non-destructive)

```powershell
Set-Location "$HOME\EVE-V4-Code"
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }
$py = '.\.venv\Scripts\python.exe'
& $py -m unittest -v v4.tests.test_storage_governor v4.tests.test_local_service v4.tests.test_hot_retention v4.tests.test_hot_cutover
if ($LASTEXITCODE -ne 0) { throw 'New storage tests failed; do not apply cutover' }
& $py -m v4.storage_governor
& $py -m v4.hot_retention
& $py -m v4.hot_cutover
Get-PSDrive -PSProvider FileSystem |
    Select-Object Name,Root,@{Name='FreeGiB';Expression={[math]::Round($_.Free / 1GB,1)}}
```

The three module invocations with no `--apply` and no `--record`
are read-only. The first local hourly scheduled scan after code pull
records telemetry, without modifying historical business evidence.

Only after the user provides a current separate-volume *verified full
backup* can the old database be safely considered for controlled
promotion. Read `v4/HOT_CUTOVER_RUNBOOK.md`; no unattended database
switchover is implemented.
