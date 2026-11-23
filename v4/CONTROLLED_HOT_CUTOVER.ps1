#requires -Version 5.1
<#
Run one guarded 72-run SQLite hot/cold promotion window.
No Start-Process -Wait: direct native invocation with live console progress.
Apply preserves old source SQLite, raw proofs, archives and D: backup.
#>
[CmdletBinding()]
param(
    [switch]$Apply,
    [string]$Ack = "",
    [string]$BackupDir = "D:\V4-Safe-Backup"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$DataRoot = Join-Path $HOME 'EVE-V4-Data'
$CodeRoot = Join-Path $HOME 'EVE-V4-Code'
$Python = Join-Path $CodeRoot '.venv\Scripts\python.exe'
$Shadow = 'EVE-V4-Shadow'
$Push = 'EVE-V4-Opportunity-Push'
$Source = Join-Path $DataRoot 'sqlite\v4-shadow.sqlite3'
$StageDir = Join-Path $DataRoot 'hot-stage'
$Paused = $false
$CheckpointBegun = $false
$PromoteBegun = $false
$Finished = $false
$TranscriptStarted = $false

function Say([string]$Message) {
    Write-Host ("[{0}] {1}" -f [DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss'), $Message)
}
function Invoke-PythonStep([string]$Name, [string[]]$PythonArgs) {
    Say "START: $Name"
    # Native stderr progress must not become PS 5.1 fatal NativeCommandError.
    $previous = $ErrorActionPreference
    $exit = -1
    try {
        $ErrorActionPreference = 'Continue'
        & $Python @PythonArgs
        $exit = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $previous }
    if ($exit -ne 0) { throw "STEP_FAILED: $Name (python exit $exit)" }
    Say "PASS: $Name"
}
function Assert-NoV4Activity {
    # Disabling Task Scheduler does not stop an already running process.
    $running = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
        $_.Name -match '^python(w)?\.exe$' -and
        $_.CommandLine -match 'v4\.(local_service|local_run|full_scan|deep_scan|opportunity_push|local_backup|external_backup|maintenance_checkpoint|hot_cutover|hot_ledger_stage|proof_cold_archive|hot_retention)'
    })
    if ($running.Count -gt 0) {
        $running | Select-Object ProcessId,Name,CommandLine | Format-List
        throw 'V4_PROCESS_ACTIVE_WAIT_FOR_SCAN_TO_FINISH_NO_FORCE_KILL'
    }
}
function Assert-TasksDisabled {
    foreach ($taskName in @($Shadow,$Push)) {
        $state = (Get-ScheduledTask -TaskName $taskName -ErrorAction Stop).State
        if ($state -ne 'Disabled') {
            throw "SCHEDULED_TASK_NOT_DISABLED: $taskName state=$state"
        }
    }
}
function New-FilesAfter([string]$Folder, [string]$Filter, [object[]]$Prior) {
    $items = @(Get-ChildItem -LiteralPath $Folder -File -Filter $Filter -ErrorAction SilentlyContinue)
    $fresh = @($items | Where-Object { $Prior -notcontains $_.FullName })
    if ($fresh.Count -ne 1) {
        throw "EXPECTED_EXACTLY_ONE_NEW_ARTIFACT:$Filter actual=$($fresh.Count)"
    }
    return $fresh[0]
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "V4_PYTHON_NOT_INSTALLED: $Python"
}
if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
    throw "V4_PRODUCTION_SQLITE_NOT_FOUND: $Source"
}
if (-not $Apply) {
    Say 'READ-ONLY preview. No scheduled tasks modified.'
    Get-ScheduledTask -TaskName $Shadow,$Push | Select-Object TaskName,State | Format-Table
    Invoke-PythonStep 'Cold archive coverage' @('-m','v4.proof_cold_archive')
    Invoke-PythonStep '72-run candidate preview' @('-m','v4.hot_ledger_stage')
    Invoke-PythonStep 'Live WAL/sidecar inspection' @('-m','v4.maintenance_checkpoint')
    Invoke-PythonStep 'Hot retention policy' @('-m','v4.hot_retention')
    Say 'Preview complete. Protected promotion requires -Apply -Ack I_ACCEPT_V4_HOT_CUTOVER.'
    exit 0
}
if ($Ack -cne 'I_ACCEPT_V4_HOT_CUTOVER') {
    throw 'EXPLICIT_OPERATOR_ACK_REQUIRED_FOR_DATABASE_PROMOTION'
}
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw 'RUN_FROM_AN_ELEVATED_ADMINISTRATOR_POWERSHELL' }
if ((Get-ScheduledTask -TaskName $Push -ErrorAction Stop).State -ne 'Disabled') {
    throw 'OPPORTUNITY_PUSH_MUST_REMAIN_DISABLED'
}
if ((Get-ScheduledTask -TaskName $Shadow -ErrorAction Stop).State -eq 'Running') {
    throw 'SHADOW_IS_RUNNING_WAIT_UNTIL_CURRENT_CYCLE_EXITS'
}
if (Test-Path -LiteralPath ($Source + '-journal')) {
    throw 'SQLITE_ROLLBACK_JOURNAL_PRESENT_INSPECT_BEFORE_MAINTENANCE'
}
Assert-NoV4Activity
# Cross-volume backup is a program gate, but C: and D: can share one disk.
# Report the hardware risk explicitly; this is NOT an off-machine restore.
try {
    $cDisk = (Get-Partition -DriveLetter C -ErrorAction Stop).DiskNumber
    $dDisk = (Get-Partition -DriveLetter D -ErrorAction Stop).DiskNumber
    Say "STORAGE_DISK_MAP: C=Disk$cDisk D=Disk$dDisk"
    if ($cDisk -eq $dDisk) {
        Write-Warning 'C and D share a physical disk. A separate offline/off-machine recovery copy is still required.'
    }
}
catch {
    Say 'PHYSICAL_DISK_LAYOUT_UNVERIFIED: off-machine recovery copy remains required.'
}

$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$LogDir = Join-Path $DataRoot 'logs'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$log = Join-Path $LogDir ("controlled-hot-cutover-" + $stamp + ".log")
Start-Transcript -LiteralPath $log -ErrorAction Stop | Out-Null
$TranscriptStarted = $true
try {
    Set-Location -LiteralPath $CodeRoot
    Invoke-PythonStep 'Acceptance tests on TEMP fixtures' @('-m','unittest','-q','v4.tests.test_maintenance_checkpoint','v4.tests.test_external_backup','v4.tests.test_hot_cutover','v4.tests.test_hot_retention','v4.tests.test_cutover_verification')
    Say 'PAUSING retained Shadow schedule (Opportunity-Push remains Disabled).'
    Disable-ScheduledTask -TaskName $Shadow -ErrorAction Stop | Out-Null
    $Paused = $true
    Assert-TasksDisabled
    Assert-NoV4Activity

    $beforeStages = @(Get-ChildItem -LiteralPath $StageDir -File -Filter 'v4-shadow-hot-*.manifest.json' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    $beforeBackups = @(Get-ChildItem -LiteralPath $BackupDir -File -Filter 'v4-shadow-full-*.sqlite3' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)

    Invoke-PythonStep 'Archive and verify ALL runs older than 72' @('-m','v4.proof_cold_archive','--apply','--all')
    Invoke-PythonStep 'Build FRESH 72-run candidate' @('-m','v4.hot_ledger_stage','--stage')
    $manifest = New-FilesAfter $StageDir 'v4-shadow-hot-*.manifest.json' $beforeStages
    $candidate = Join-Path $StageDir ($manifest.Name.Replace('.manifest.json','.sqlite3'))
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { throw 'NEW_HOT_SQLITE_NOT_FOUND' }
    Invoke-PythonStep 'Verify stage SHA256 and full scan-run freshness' @('-m','v4.hot_cutover_preflight','--candidate',$candidate,'--verify-hash')

    # A D backup from an earlier scan is stale. Create a current fresh one.
    Invoke-PythonStep 'Create + integrity verify NEW full D backup' @('-m','v4.external_backup','--backup-dir',$BackupDir,'--create')
    $backup = New-FilesAfter $BackupDir 'v4-shadow-full-*.sqlite3' $beforeBackups
    Say "NEW VERIFIED D BACKUP: $($backup.FullName)"
    if ($backup.Length -lt 1024) { throw 'NEW_D_BACKUP_EMPTY' }

    Assert-TasksDisabled
    Assert-NoV4Activity
    $CheckpointBegun = $true
    Invoke-PythonStep 'SQLite-owned source WAL checkpoint' @('-m','v4.maintenance_checkpoint','--apply','--external-backup',$backup.FullName,'--ack','I_ACCEPT_V4_SQLITE_CHECKPOINT')

    Assert-TasksDisabled
    Assert-NoV4Activity
    $PromoteBegun = $true
    Invoke-PythonStep 'PROMOTE guarded hot DB; preserve FULL old DB' @('-m','v4.hot_cutover','--apply','--candidate',$candidate,'--external-backup',$backup.FullName,'--ack','I_ACCEPT_V4_HOT_CUTOVER')
    Invoke-PythonStep 'Read-only 72-run post-promotion audit' @('-m','v4.cutover_verification')
    $Finished = $true

    Say 'RE-ENABLING ONLY retained Shadow schedule.'
    Enable-ScheduledTask -TaskName $Shadow -ErrorAction Stop | Out-Null
    $Paused = $false
    if ((Get-ScheduledTask -TaskName $Push).State -ne 'Disabled') {
        throw 'UNEXPECTED_FORMAL_PUSH_TASK_STATE'
    }
    Get-ScheduledTask -TaskName $Shadow,$Push | Select-Object TaskName,State | Format-Table
    Say 'CUTOVER_ACTIVATED_SHADOW_RESUMED; next real scan/email audit is still required.'
    Say "LOG: $log"
}
catch {
    Say "CUTOVER_STOPPED: $($_.Exception.Message)"
    if ($Paused -and -not $CheckpointBegun -and -not $PromoteBegun) {
        # The original production DB has not been altered by these steps.
        if (Test-Path -LiteralPath $Source -PathType Leaf) {
            Say 'Pre-checkpoint interruption: restoring only Shadow scheduler.'
            Enable-ScheduledTask -TaskName $Shadow -ErrorAction Stop | Out-Null
            $Paused = $false
        }
    }
    elseif ($Paused) {
        # May have modified SQLite journaling or renamed production DB.
        Say 'CRITICAL: Shadow remains DISABLED for guarded operator inspection.'
        Say 'Do NOT manually delete WAL/SHM or swap back databases.'
    }
    throw
}
finally {
    Say "PHASE: paused=$Paused checkpoint_started=$CheckpointBegun promotion_started=$PromoteBegun verified=$Finished"
    Get-ScheduledTask -TaskName $Shadow,$Push | Select-Object TaskName,State | Format-Table
    Say "LOG: $log"
    if ($TranscriptStarted) { Stop-Transcript -ErrorAction SilentlyContinue | Out-Null }
}
