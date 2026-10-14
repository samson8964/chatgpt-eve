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
# Independent SQL check, no mail and no secret reads.
& $python -m v4.local_status --data-root $DataRoot | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Local SQLite diagnostics failed.' }
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
