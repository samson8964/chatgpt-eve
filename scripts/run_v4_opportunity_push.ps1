# Hourly EVE V4 market opportunity runner; hidden Windows Task Scheduler.
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
$data = Join-Path $HOME 'EVE-V4-Data'
$logdir = Join-Path $data 'logs'
New-Item -ItemType Directory -Force -Path $logdir | Out-Null
$logfile = Join-Path $logdir 'opportunity-push.log'
Set-Location $repo
try {
    if (-not (Test-Path -LiteralPath $python)) { throw 'V4_PYTHON_NOT_FOUND' }
    Add-Content -LiteralPath $logfile -Value ("START " + (Get-Date -Format o)) -Encoding UTF8
    & $python -m v4.opportunity_push --data-root $data 2>&1 |
        Out-String | Add-Content -LiteralPath $logfile -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw ("OPPORTUNITY_PUSH_EXIT_" + $LASTEXITCODE) }
    Add-Content -LiteralPath $logfile -Value ("FINISH " + (Get-Date -Format o)) -Encoding UTF8
} catch {
    Add-Content -LiteralPath $logfile -Value ("FAILED " + (Get-Date -Format o) + " " + $_.Exception.GetType().Name) -Encoding UTF8
    exit 2
}