<# Install backup task and switch hourly task, fail closed.
No backup, scan, cleanup or email is launched by this installer.
Hourly task must be Disabled and have no active v4.local_service processes.
Installer will leave hourly task Disabled for safe mail catch-up and user resume.
#>
[CmdletBinding()]
param(
  [string]$CodeRoot = "$env:USERPROFILE\EVE-V4-Code",
  [string]$DataRoot = "$env:USERPROFILE\EVE-V4-Data",
  [string]$DailyAt = '03:45'
)
$ErrorActionPreference = 'Stop'
$shadowName = 'EVE-V4-Shadow'
$backupName = 'EVE-V4-Daily-Backup'
$shadow = Get-ScheduledTask -TaskName $shadowName -ErrorAction Stop
if ($shadow.State -ne 'Disabled') {
  throw 'SHADOW_MUST_BE_DISABLED_BEFORE_TASK_CHANGE'
}
$active = @(Get-CimInstance Win32_Process | Where-Object {
  $_.Name -match '^pythonw?\.exe$' -and
  $_.CommandLine -match '-m\s+v4\.local_service'
})
if ($active.Count -gt 0) {
  throw 'SHADOW_PROCESS_STILL_ACTIVE_REFUSE_TASK_CHANGE'
}
if (@($shadow.Actions).Count -ne 1) {
  throw 'SHADOW_MULTIPLE_ACTIONS_REFUSE_CHANGE'
}
$original = $shadow.Actions[0]
if ($original.Execute -notlike '*pythonw.exe' -or
    $original.Arguments -notmatch '-m\s+v4\.local_service' -or
    $original.Arguments -match '--backup-mode') {
  throw 'SHADOW_COMMAND_UNEXPECTED_REFUSE_CHANGE'
}
$existing = Get-ScheduledTask -TaskName $backupName -ErrorAction SilentlyContinue
if ($existing) {
  throw 'BACKUP_TASK_ALREADY_EXISTS_REFUSE_CHANGE'
}
$pythonw = Join-Path $CodeRoot '.venv\Scripts\pythonw.exe'
$python = Join-Path $CodeRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonw) -or !(Test-Path -LiteralPath $python)) {
  throw 'V4_VENV_MISSING'
}
Push-Location $CodeRoot
try {
  & $python -m unittest -q v4.tests.test_daily_backup_job v4.tests.test_local_service
  if ($LASTEXITCODE -ne 0) { throw 'V4_DAILY_BACKUP_TESTS_FAILED' }
} finally { Pop-Location }
$backupAction = New-ScheduledTaskAction -Execute $pythonw -Argument ('-m v4.daily_backup_job --data-root "' + $DataRoot + '"') -WorkingDirectory $CodeRoot
$backupTrigger = New-ScheduledTaskTrigger -Daily -At $DailyAt
$backupSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 12)
$hourlyAction = New-ScheduledTaskAction -Execute $original.Execute -Argument ($original.Arguments.Trim() + ' --backup-mode external') -WorkingDirectory $original.WorkingDirectory
$registered = $false
try {
  Register-ScheduledTask -TaskName $backupName -Action $backupAction -Trigger $backupTrigger -Principal $shadow.Principal -Settings $backupSettings -ErrorAction Stop | Out-Null
  $registered = $true
  $check = Get-ScheduledTask -TaskName $backupName -ErrorAction Stop
  if ($check.State -eq 'Disabled') { throw 'BACKUP_TASK_REGISTERED_DISABLED' }
  Set-ScheduledTask -TaskName $shadowName -Action $hourlyAction -ErrorAction Stop | Out-Null
  $updated = Get-ScheduledTask -TaskName $shadowName -ErrorAction Stop
  if ($updated.Actions[0].Arguments -notmatch '--backup-mode\s+external') {
    throw 'SHADOW_BACKUP_MODE_SWITCH_NOT_SAVED'
  }
  if ($updated.State -ne 'Disabled') {
    throw 'SHADOW_MUST_STAY_DISABLED_UNTIL_MAIL_CATCHUP_AND_EXPLICIT_RESUME'
  }
  Write-Host 'V4_DAILY_BACKUP_DECOUPLING_INSTALLED'
  Write-Host 'Hourly scan and research mail no longer wait for the full SQLite backup.'
  Write-Host 'Independent daily task retains full verification and safe rotation.'
  Get-ScheduledTask -TaskName $shadowName,$backupName | Select-Object TaskName,State
}
catch {
  try { Set-ScheduledTask -TaskName $shadowName -Action $original -ErrorAction Stop | Out-Null }
  catch { Write-Warning 'MANUAL_ROLLBACK_REQUIRED_FOR_HOURLY_SHADOW_ACTION' }
  if ($registered) {
    try { Unregister-ScheduledTask -TaskName $backupName -Confirm:$false -ErrorAction Stop }
    catch { Write-Warning 'MANUAL_REVIEW_REQUIRED_FOR_DAILY_BACKUP_TASK' }
  }
  throw
}
