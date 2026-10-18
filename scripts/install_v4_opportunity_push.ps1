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
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Hours 2)
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 40) -StartWhenAvailable
Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $task
Write-Output 'OPPORTUNITY_PUSH_TASK_INSTALLED_AND_START_REQUESTED'
Write-Output "ACCOUNT $user"
Write-Output "TASK $task"
Write-Output "LOG $(Join-Path $HOME 'EVE-V4-Data\logs\opportunity-push.log')"
Write-Output 'Existing V4 shadow task, game-mail configuration and retired V3 remain untouched.'
