# One-time install and immediate start: every 2 hours under current user.
# Does not modify EVE-V4-Shadow or re-enable retired V3.
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'WINDOWS_REQUIRED' }
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
$run = Join-Path $PSScriptRoot 'run_v4_opportunity_push.ps1'
if (-not (Test-Path -LiteralPath $python)) { throw 'V4_PYTHON_NOT_FOUND' }
if (-not (Test-Path -LiteralPath $run)) { throw 'V4_OPPORTUNITY_RUNNER_MISSING' }
$task = 'EVE-V4-Opportunity-Push'
$command = "powershell.exe -NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$run`""
& schtasks.exe /Create /TN $task /TR $command /SC HOURLY /MO 2 /ST 00:55 /F
if ($LASTEXITCODE -ne 0) { throw 'CREATE_OPPORTUNITY_TASK_FAILED' }
& schtasks.exe /Run /TN $task
if ($LASTEXITCODE -ne 0) { throw 'START_OPPORTUNITY_TASK_FAILED' }
Write-Output 'OPPORTUNITY_PUSH_TASK_INSTALLED_AND_START_REQUESTED'
Write-Output "TASK $task"
Write-Output "LOG $(Join-Path $HOME 'EVE-V4-Data\logs\opportunity-push.log')"
Write-Output 'Existing V4 shadow and retired V3 remain untouched.'
