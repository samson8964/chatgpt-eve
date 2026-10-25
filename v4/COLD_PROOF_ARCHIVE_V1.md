# V4 main SQLite growth: lossless cold-proof archive and bounded hot-stage

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
