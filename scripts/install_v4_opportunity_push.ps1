# One-time installation and immediate first run, using CURRENT Windows account
# whose Windows Credential Manager already holds V4 Gmail and EVE bridge secrets.
# Do NOT install as SYSTEM: that account cannot read the user's saved credentials.
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'WINDOWS_REQUIRED' }
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
$run = Join-Path $PSScriptRoot 'run_v4_opportunity_push.ps1'
if (-not (Test-Path -LiteralPath $python)) { throw 'V4_PYTHON_NOT_FOUND' }
if (-not (Test-Path -LiteralPath $run)) { throw 'V4_OPPORTUNITY_RUNNER_MISSING' }
$task = 'EVE-V4-Opportunity-Push'
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$exe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$arg = ('-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $run)
$action = New-ScheduledTaskAction -Execute $exe -Argument $arg -WorkingDirectory $repo
# Keep the independent new-Jita opportunity lane away from the existing :23 V4 shadow scan.
# Re-registering an existing task should not itself create a second ad-hoc scan.
$now = Get-Date
$next = $now.Date.AddHours($now.Hour).AddMinutes(45)
if ($next -le $now.AddMinutes(2)) { $next = $next.AddHours(1) }
$trigger = New-ScheduledTaskTrigger -Once -At $next -RepetitionInterval (New-TimeSpan -Hours 1)
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 40) -StartWhenAvailable
$existing = Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
if (-not $existing) {
    Start-ScheduledTask -TaskName $task
    Write-Output 'OPPORTUNITY_PUSH_NEW_TASK_FIRST_RUN_REQUESTED'
} else {
    Write-Output 'OPPORTUNITY_PUSH_TASK_UPDATED_HOURLY_NO_EXTRA_RUN'
}
Write-Output "ACCOUNT $user"
Write-Output "TASK $task"
Write-Output "NEXT_HOURLY_TRIGGER $next"
Write-Output "LOG $(Join-Path $HOME 'EVE-V4-Data\logs\opportunity-push.log')"
Write-Output 'Existing V4 shadow task, game-mail configuration and retired V3 remain untouched.'
