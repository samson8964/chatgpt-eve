# EVE V4 LOCAL SHADOW ONLY. Run in Windows PowerShell; does not change V3 or GitHub cron.
# Install is opt-in. Task runs only while the current user remains signed in.
# 12 fixed daily triggers avoid repetition-duration expiration or drift.
param(
    [switch]$Install,
    [string]$DataRoot = (Join-Path $HOME 'EVE-V4-Data'),
    [string]$TaskName = 'EVE-V4-Shadow'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonw = Join-Path $repo '.venv\Scripts\pythonw.exe'
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw "Missing virtual Python: $python" }
if (-not (Test-Path $pythonw)) { throw "Missing windowless Python: $pythonw" }
if (-not (Test-Path (Join-Path $DataRoot 'sqlite\v4-shadow.sqlite3'))) {
    throw 'No verified local SQLite shadow ledger; run one foreground scan first.'
}
# Fail closed: install is permitted only after a complete, SQL-audited,
# non-email shadow run. Never mistake SHADOW_RECORDED partial coverage for
# permission to register an unattended schedule.
$statusJson = & $python -m v4.local_status --data-root $DataRoot
if ($LASTEXITCODE -ne 0) { throw 'Local SQLite diagnostics failed.' }
try {
    $status = $statusJson | ConvertFrom-Json -ErrorAction Stop
} catch {
    throw 'Local SQLite diagnostics returned invalid JSON.'
}
if ($status.run_status -ne 'SHADOW_RECORDED' -or
    $status.coverage_gate -ne 'INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED' -or
    $status.source_input_integrity -ne 'ALL_PARSED' -or
    $status.sqlite_integrity -ne 'ok' -or
    $status.sqlite_count_matches_report -ne $true -or
    $status.mail_enabled -ne $false -or
    $status.ready_for_production -ne $false) {
    throw 'LATEST_SHADOW_RUN_NOT_FULLY_VERIFIED_FOR_UNATTENDED_MODE'
}
# Read the same approved source registry used by scheduled V4 Python jobs.
$lanesJson = & $python -c 'import json; from v4.structure_registry import STRUCTURES; print(json.dumps(list(STRUCTURES)))'
if ($LASTEXITCODE -ne 0) { throw 'V4_STRUCTURE_REGISTRY_UNAVAILABLE' }
$laneNames = @($lanesJson | ConvertFrom-Json -ErrorAction Stop)
if ($laneNames.Count -lt 3) { throw 'V4_STRUCTURE_REGISTRY_INCOMPLETE' }
foreach ($lane in $laneNames) {
    $info = $status.structure_health.$lane
    if ($null -eq $info -or $info.status -ne 'COMPLETE' -or
        $null -eq $info.pages -or $info.pages -lt 1 -or
        $info.pages_fetched -ne $info.pages -or $info.orders -lt 0) {
        throw ('STRUCTURE_LANE_NOT_COMPLETE: ' + $lane)
    }
}
Write-Host ('Verified last run: public + ' + $laneNames.Count + ' structure markets COMPLETE; SQLite audit OK; MAIL OFF.')
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    throw "Task already exists: $TaskName. Refusing to overwrite."
}
if (-not $Install) {
    Write-Host 'DRY RUN: task was not registered.'
    Write-Host "Name: $TaskName"
    Write-Host 'Schedule: every two hours at :23 local time, 12 daily triggers.'
    Write-Host 'Mode: SHADOW ONLY; existing emails and cloud jobs unchanged.'
    Write-Host 'Runs as the signed-in Windows user, without admin rights.'
    Write-Host 'Run the same command with -Install only when ready.'
    return
}
$action = New-ScheduledTaskAction -Execute $pythonw -WorkingDirectory $repo -Argument ('-m v4.local_service --data-root "' + $DataRoot + '"')
$triggers = @()
for ($hour=0; $hour -lt 24; $hour+=2) {
    $triggers += New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours($hour).AddMinutes(23))
}
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 85) -StartWhenAvailable
$who = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $who -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Description 'EVE V4 read-only SHADOW market scans and local SQLite audit only; NO MAIL.' -ErrorAction Stop | Out-Null
$created = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
Write-Host ('Registered task: ' + $created.TaskName + ' | State: ' + $created.State)
Write-Host "Next runs: every two hours at :23 while signed in."
Write-Host ('Logs: ' + (Join-Path $DataRoot 'logs\shadow-task.log'))
