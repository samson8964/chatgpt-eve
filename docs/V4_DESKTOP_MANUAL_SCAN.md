# V4 desktop monitor: manual complete scan

V4 desktop widget now has an explicit **立即全面扫描** button. It does **not** fork another data miner or bypass its scheduled task. It submits `Start-ScheduledTask -InputObject $t` for the existing `EVE-V4-Shadow` job. The normal `v4.local_service` performs source freshness checks, full public-market/contract census, the three authorized structure market scans, deep valuation, persistence and optionally configured Gmail / in-game research digest delivery.

## Safety

- Only the explicit user click triggers an unscheduled run; status polling never triggers a scan.
- Windows Task Scheduler must report `Ready`, `MultipleInstances=IgnoreNew`, and exactly one PythonW action whose args invoke `-m v4.local_service`. Other states or altered task definitions will be rejected.
- The button disables during request submission and while the task is `Running`; the existing task's IgnoreNew policy prevents duplicate instances during the scheduled overlap race.
- The PowerShell call is off the Tk main thread with a 15s timeout; no console window, admin elevation, secrets, or credentials are displayed.
- On a successful start request, the widget says "启动请求已提交" until the task state/last run time confirms a trigger. It never claims the scan itself succeeded before the independent status/log verifies it.
- If EVE Ref snapshots exceed existing age thresholds, the normal full-scan pipeline safely records `SKIPPED_UPSTREAM_STALE` and no digest is sent. Manual trigger must never override this integrity gate.
- The existing two research-mail channels, existing configured recipients, volume annotations, ship/freighter exclusions and financial gates remain exactly the same.

## Install update on Windows

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only
& .\.venv\Scripts\python.exe -m unittest v4.tests.test_manual_scan -v
```

Close the existing V4 monitor via × and reopen it using the user's original monitor launch shortcut. The running PythonW monitor won't pick up updated files until restarted. Do not reinstall or replace `EVE-V4-Shadow`. Click the new button only while the task is `Ready`. After clicking, the normal task logs remain at `EVE-V4-Data\logs\shadow-task.log`. The future schedule is unchanged.

## Verify manual execution

```powershell
Get-ScheduledTask -TaskName 'EVE-V4-Shadow' |
  Select-Object TaskName, State
Get-ScheduledTaskInfo -TaskName 'EVE-V4-Shadow' |
  Select-Object LastRunTime,LastTaskResult,NextRunTime
Get-Content "$HOME\EVE-V4-Data\logs\shadow-task.log" -Tail 30
```

Expected successful scan: latest status `SHADOW_RECORDED` and, if configured, `REVIEW_MAIL` and `GAME_REVIEW_MAIL` receipts. An upstream-stale skip is an intentional no-data cycle, not a failed download or opportunity-alert run.