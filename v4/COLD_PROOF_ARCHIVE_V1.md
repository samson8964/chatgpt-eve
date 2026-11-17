# V4 main SQLite growth: lossless cold-proof archive and bounded hot-stage

## Phase-2 real Windows milestone: 2026-10-25

User supplied a successful full Windows run:

- 22 unit tests OK.
- 244 scan_runs (at sample time), 72 recent hot, 172 cold.
- 172/172 old runs archived and integrity verified:
  `archived_this_call=169`, `verified_existing=3`, failed=[].
- Successfully staged a 7.782 GiB candidate with 4,590,360 hot proof
  rows and all 244 scan_runs metadata. Prior production SQLite was
  approximately 23.162 GiB. **STAGED_NOT_ACTIVATED**: no live disk
  space has yet been reclaimed.
- Subsequent hourly scans may make the first staged candidate STALE.

## Long-term growth control (new code, not yet activated)

- `v4/hot_ledger_stage.py` now provisions `auto_vacuum=INCREMENTAL`
  on the *new empty* candidate database, before schema creation.
  This is necessary to reclaim pages incrementally during future
  housekeeping; it cannot be safely backported to an existing live
  database by a no-op PRAGMA.
- It also writes `v4_hot_policy` as *inactive* and
  `v4_cold_proofs` with an index of each old run's verified gzip
  SHA256, raw SHA256, proof count and archive timestamp.
- `v4/hot_retention.py` is the continuous bounded maintenance worker.
  It refuses ANY deletion against the currently deployed legacy DB or
  a staged-but-inactive candidate; deletion requires an explicit
  activation marker, correct schema and `auto_vacuum=INCREMENTAL`.
  When activated, one old run is archived and verified, its duplicate
  SQLite proof rows are transactionally removed, a cold index entry
  remains, and at most 25,000 SQLite free pages are reclaimed.
- `v4/local_service.py` now calls hot retention **after** attempting
  both research mail channels; exceptions cannot alter mail delivery
  status. Current legacy SQLite returns `NOT_ENABLED`, safely.
- `v4/hot_cutover_preflight.py` is read-only and checks the staged
  candidate against current live run metadata, retained proof counts,
  cold index completeness and its sealed SHA256 (with --verify-hash).
  New scans since the stage make it return `NOT_READY`. It does not
  activate or move files. **A production cutover/rollback tool is
  NOT implemented in these commits.**

### Validate new long-term code on Windows

```powershell
Set-Location "$HOME\EVE-V4-Code"
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git update blocked' }
& .\.venv\Scripts\python.exe -m unittest -v `
  v4.tests.test_hot_retention `
  v4.tests.test_hot_ledger_stage `
  v4.tests.test_proof_cold_archive `
  v4.tests.test_local_service `
  v4.tests.test_local_store `
  v4.tests.test_storage_audit
if ($LASTEXITCODE -ne 0) { throw 'Do not proceed: tests failed' }
```

The 7.782 GiB candidate from the previous run was built before the
incremental-vacuum marker change, so it **must not be activated**.
After these tests pass, a NEW candidate can be built by running
`python -m v4.hot_ledger_stage --stage` (older candidate remains
untouched). First check disk space and active backup jobs. Verify
preflight with `python -m v4.hot_cutover_preflight --verify-hash`.
This checks the newest candidate and will fail if hourly scans have
added newer rows in the meantime.

Do not swap SQLite files manually. The controlled task pause,
independent backup, delta catchup, activation and rollback are separate
remaining work. Automatic retention exists in source only and remains
safe-disabled until a complete controlled deployment.

## Status

**Implemented as offline preparation, NOT activated.** The live
`sqlite/v4-shadow.sqlite3`, scheduled hourly scans, two mail channels,
market/contract scans, existing backups and `runs/` are untouched by these
tools. No production run ever invokes them automatically.

Observed 2026-10-24: 23.162 GiB hot DB, 235 scan_runs,
13,788,412 proof_versions; recent scans around 63.5k proofs/run.
The 128-row payload sample averaged 1,230 bytes of JSON per row
(estimated 15.79 GiB just for proof_json).

Root cause: `v4.deep_scan` generates
`runs/<timestamp>/all_proofs.jsonl`; `v4.local_store.persist` also
re-inserts normalized JSON for every run into `proof_versions` with
primary key (run_id, instance), so historical full snapshots accumulate.

## Safety invariant

**Do not DELETE proofs, VACUUM the live database, remove WAL/SHM,
stop alerts, or replace production SQLite based on a size estimate.**
A cold gzip archive is not considered valid without all of:
1. SQLite verified run ID/status/proof_count/raw proof_sha256.
2. Original `all_proofs.jsonl` verified byte-for-byte against that SHA
   and matching nonblank line count.
3. Archived gzip uncompressed round-trip SHA and count agree.
4. Archived gzip SHA and complete manifest are written.
5. A separate independent/off-machine backup exists prior to any eventual
   live migration and a successful cold restore has been demonstrated.

Each cold archive is named by immutable run ID, never overwrites an
existing archive, contains **exact original raw JSONL bytes** (not a
lossy summarized substitute), and its companion manifest is published
last. Interrupted or inconsistent work fails closed with no source
deletion.

### 2026-10-25 Windows 1/40 test failure and correction

The operator's Windows Python test showed that the 500 KiB overflow-page
fixture archived and deleted one expired run correctly, but
`vacuum_pages_reclaimed` was **1**, violating the test expectation
that >20 SQLite pages be reclaimed. All other tests passed and the
legacy production ledger returned `NOT_ENABLED`, `sqlite_modified=false`.
The user did not activate any hot policy.

According to the official SQLite PRAGMA specification,
`incremental_vacuum(N)` is permitted to reclaim *up to* N pages,
not necessarily N in one invocation. The maintenance helper now
repeats the pragma while it observes real page reductions, bounded
by requested page count and a 20-second time ceiling; it
exposes `vacuum_freelist_before/after`,
`vacuum_page_count_before/after`, `vacuum_passes` and
`vacuum_incomplete` for diagnosis. The overflow-page test emits
all these diagnostics on failure. An additional regression test
simulates SQLite reclaiming just one page per PRAGMA call and checks
that 40 pages are reclaimed over 40 bounded passes.

The new helper was validated on a small synthetic SQLite sample
where the one-page-per-call simulation reclaimed exactly 40 pages
(`free_before=122,free_after=82`). It has NOT yet passed the
user's Windows regression suite; do NOT cut over until it does.

## Stage A — pull and test (Windows PowerShell)

```powershell
Set-Location "$HOME\EVE-V4-Code"
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw "Git pull failed" }
& .\.venv\Scripts\python.exe -m unittest -v `
  v4.tests.test_proof_cold_archive `
  v4.tests.test_hot_ledger_stage `
  v4.tests.test_local_store `
  v4.tests.test_storage_audit
if ($LASTEXITCODE -ne 0) { throw "Do not archive: tests failed" }
```

These tests use SMALL temporary database fixtures, not the production
23+ GiB database. The pilot MUST be revalidated on Windows after pull.

## Stage B — read-only cold-source inventory

```powershell
& .\.venv\Scripts\python.exe -m v4.proof_cold_archive
& .\.venv\Scripts\python.exe -m v4.hot_ledger_stage
```

Output provides `cold_run_candidates`, `missing_raw_source_count`,
`unverified_run_count`, `missing_archives` and `can_stage`.
Only runs beyond latest 72 verified historical runs are eligible by
default. Check missing source samples before starting export.

## Stage C — **pilot 3 runs** (does not touch SQLite)

```powershell
& .\.venv\Scripts\python.exe -m v4.proof_cold_archive --apply --limit 3
```

This writes at most 3 verified cold gzip files and manifest JSONs to
`$HOME\EVE-V4-Data\cold-proof-archives\`. It never deletes any
original `runs/` artifact and never opens live SQLite writable.
Each subsequent call advances past already archived verified runs.

Review compression results, disk free space, content verification and
errors before deciding to perform one longer batch.

## Stage D — remaining old runs (explicit opt-in)

```powershell
& .\.venv\Scripts\python.exe -m v4.proof_cold_archive --apply --all
```

Long-running disk I/O is expected. The exporter is resumable; invoking
it again checks existing cold manifests against their on-disk gzip.
It enforces >=30 GiB available free space before writing each new run.
An incomplete source leads to `PARTIAL_BLOCKED` (CLI exit code 2)
and **no source database deletion**. Do not run a second exporter
concurrently. If archival is interrupted, running the same command again
verifies completed archives before processing the remaining runs.

## Stage E — optional hot DB candidate, NEVER activated by this script

```powershell
& .\.venv\Scripts\python.exe -m v4.hot_ledger_stage
# Only if can_stage=true and all old archives verify:
& .\.venv\Scripts\python.exe -m v4.hot_ledger_stage --stage
```

The staged SQLite is created under `EVE-V4-Data/hot-stage/`.
It keeps the `scan_runs` metadata for **all** historical runs but
full `proof_versions` only for newest 72 runs. Every older run is
required to have a lossless, verified cold archive. The candidate
passes `PRAGMA integrity_check`, is given a separate sha256 manifest,
and is marked `STAGED_NOT_ACTIVATED`. 35 GiB free-space guard.

If a new scan completes during archival validation, the stage operation
aborts with `LIVE_RUN_SET_CHANGED_RETRY_PREPARATION`, rather than
silently dropping new work. This is a **conservative safety outcome**.
Prefer to stage under a controlled shadow-task maintenance window.

## Why production is not switched yet

A safe Windows cutover requires, in order:
- Entire historical cold archive verified and restorable on the local
  host, with an independent off-machine copy.
- Explicit maintenance of `EVE-V4-Shadow` (pause scheduled hourly
  shadow writes, prevent re-entry); verify formal opportunity push
  remains isolated.
- Final delta catch-up for runs produced after the staged snapshot.
- WAL checkpoint and tested restore/rollback for Windows file locks.
- Atomic swap only after candidate counts, hashes and integrity match,
  with original DB preserved as an independent rollback artifact.
- New bounded-history storage policy: archive each completed run and
  periodically rebuild a recent-run hot DB, or write old proofs directly
  to cold storage, to prevent recurrence after the one-time cutover.

None of the above production-switching steps are currently automated
by this commit. **Stage success is NOT permission to manually replace
SQLite files or erase backup snapshots.**

## Related commands

```powershell
& .\.venv\Scripts\python.exe -m v4.storage_audit --deep
```

Report observed 3-day backup rotation continues unchanged. Cold proof
archives are independent from daily database backups and must never be
treated as a replacement for full disaster recovery backups.
