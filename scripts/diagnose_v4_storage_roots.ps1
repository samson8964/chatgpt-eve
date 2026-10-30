<#
Read-only, one-shot EVE V4 storage-path and retention diagnosis.
No mail, backup, cleanup, scans, task mutation, database access or deletes.
#>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
function Write-V4Heading([string]$name) { Write-Host ([Environment]::NewLine + '=== ' + $name + ' ===') }
function Get-V4RootFromArgs([string]$arguments) {
    if ($arguments -match '--data-root\s+(?:"([^"]+)"|([^\s]+))') {
        if ($Matches[1]) { return $Matches[1] }
        return $Matches[2]
    }
    return (Join-Path $env:USERPROFILE 'EVE-V4-Data')
}
function Get-V4RecentJson([string]$logPath, [string]$prefix) {
    if (-not (Test-Path -LiteralPath $logPath)) { return $null }
    $lines = @(Get-Content -LiteralPath $logPath -Encoding UTF8 -Tail 150 -ErrorAction SilentlyContinue)
    $line = $lines | Where-Object { $_.StartsWith($prefix + ' ') } | Select-Object -Last 1
    if (-not $line) { return $null }
    try { return ($line.Substring($prefix.Length + 1) | ConvertFrom-Json -ErrorAction Stop) }
    catch { return $null }
}
function Get-V4CategoryGiB([string]$path) {
    if (-not (Test-Path -LiteralPath $path -PathType Container)) { return $null }
    $bytes = 0.0
    Get-ChildItem -LiteralPath $path -File -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
        $bytes += [double]$_.Length
    }
    return [math]::Round($bytes / 1GB, 2)
}

Write-V4Heading '1 C AND D DRIVE FREE SPACE'
Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:' OR DeviceID='D:'" |
  Select-Object DeviceID, VolumeName,
    @{N='TotalGiB';E={[math]::Round($_.Size/1GB,2)}},
    @{N='FreeGiB';E={[math]::Round($_.FreeSpace/1GB,2)}} |
  Format-Table -AutoSize

Write-V4Heading '2 ACTUAL SCHEDULED TASK DATA ROOTS'
$roots = @()
$taskRows = @()
foreach ($name in @('EVE-V4-Shadow', 'EVE-V4-Daily-Backup', 'EVE-V4-Opportunity-Push')) {
    $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if (-not $task) {
        $taskRows += [pscustomobject]@{Task=$name;State='NOT_FOUND';Module='';DataRoot='';LastCode=''}
        continue
    }
    $taskInfo = Get-ScheduledTaskInfo -TaskName $name -ErrorAction SilentlyContinue
    foreach ($action in @($task.Actions)) {
        $arguments = [string]$action.Arguments
        $module = 'UNKNOWN'
        if ($arguments -match '-m\s+(v4\.[A-Za-z0-9_]+)') {$module=$Matches[1]}
        $root = Get-V4RootFromArgs $arguments
        $roots += $root
        $taskRows += [pscustomobject]@{
            Task=$name;State=[string]$task.State;Module=$module;
            DataRoot=$root;LastCode=$(if($taskInfo){$taskInfo.LastTaskResult}else{'?'})
        }
    }
}
$taskRows | Format-Table -AutoSize -Wrap
$roots += (Join-Path $env:USERPROFILE 'EVE-V4-Data')
$roots += 'D:\EVE-V4-Data'
$roots = @($roots | Where-Object {$_} | Select-Object -Unique)

Write-V4Heading '3 DATA ROOT AND LINK CHECK'
foreach ($root in $roots) {
    if (Test-Path -LiteralPath $root -PathType Container) {
        $item = Get-Item -LiteralPath $root -Force
        $target = if($item.Target){$item.Target -join ','}else{'none'}
        Write-Host "ROOT: $root | Exists=True | Attributes=$($item.Attributes) | Target=$target"
    } else {
        Write-Host "ROOT: $root | Exists=False"
    }
}

Write-V4Heading '4 CAPACITY GOVERNOR AND DAILY BACKUP BY ACTUAL ROOT'
foreach ($root in $roots) {
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }
    Write-Host "ROOT: $root"
    $scanLog = Join-Path $root 'logs\shadow-task.log'
    $health = Get-V4RecentJson $scanLog 'STORAGE_GOVERNOR'
    if ($health) {
        $daily = $health.growth.daily_free_gib_change
        $days = $health.growth.days_until_20_gib
        Write-Host "LATEST_GOVERNOR: severity=$($health.severity); free=$($health.free_gib)GiB; total=$($health.total_gib)GiB; project=$($health.project_gib)GiB; trend=$daily GiB/day; days_to_20GiB=$days"
        if ($health.sections) {
            foreach ($part in @('sqlite','runs','backups','hot-stage','cold-proof-archives','esi-parallel-validation')) {
                $v = $health.sections.$part.gib
                Write-Host "CATEGORY: $part = $v GiB"
            }
        }
    }else{Write-Host 'LATEST_GOVERNOR: NONE IN LATEST 150 LOG LINES'}
    $backlog = Join-Path $root 'logs\daily-backup-task.log'
    if (Test-Path -LiteralPath $backlog) {
        $logs = @(Get-Content -LiteralPath $backlog -Encoding UTF8 -Tail 100 -ErrorAction SilentlyContinue)
        foreach ($row in ($logs | Where-Object {$_ -match '^DAILY_BACKUP_(TASK_STARTED|JOB_START|TASK_RESULT|TASK_FAILED)' } | Select-Object -Last 8)) {
            if ($row.StartsWith('DAILY_BACKUP_TASK_RESULT ')) {
                try{
                    $v = $row.Substring('DAILY_BACKUP_TASK_RESULT '.Length) | ConvertFrom-Json
                    Write-Host "DAILY_RESULT: status=$($v.status); new=$($v.backup_created); rotate=$($v.backup_retention.status); deleted=$($v.backup_retention.deleted); blocked=$($v.backup_retention.error_type)"
                }catch{Write-Host 'DAILY_RESULT: PARSE_FAILED'}
            } else { Write-Host ("DAILY_LOG: " + $row.Substring(0,[math]::Min(200,$row.Length))) }
        }
    }else{Write-Host 'DAILY_LOG: MISSING'}
    $rot = Join-Path $root 'logs\manual-retention.log'
    if (Test-Path -LiteralPath $rot) {
        $r = @(Get-Content -LiteralPath $rot -Encoding UTF8 -Tail 60 -ErrorAction SilentlyContinue)
        $last = $r | Where-Object {$_ -match 'BACKUP_VERIFY_|"status"|"reclaimed_gib"|"deleted"' } | Select-Object -Last 5
        foreach($line in $last){Write-Host "MANUAL_ROTATION: $line"}
    }
    $backupFolder = Join-Path $root 'backups'
    $backups = @(Get-ChildItem -LiteralPath $backupFolder -Filter 'v4-shadow-*.sqlite3' -File -ErrorAction SilentlyContinue | Sort-Object Name -Descending)
    $total = 0.0
    foreach ($f in $backups){$total += [double]$f.Length}
    Write-Host "BACKUPS: count=$($backups.Count); total_gib=$([math]::Round($total/1GB,2))"
    foreach ($f in ($backups | Select-Object -First 6)){
        Write-Host "BACKUP_FILE: $($f.Name) | GiB=$([math]::Round($f.Length/1GB,2)) | modified=$($f.LastWriteTime)"
    }
    foreach($part in @('sqlite','runs','hot-stage','cold-proof-archives','esi-parallel-validation')){
        $gib=Get-V4CategoryGiB (Join-Path $root $part)
        if ($null -ne $gib) { Write-Host "ON_DISK: $part = $gib GiB" }
    }
    Write-Host "ROLLING72_POLICY_PRESENT: $(Test-Path -LiteralPath (Join-Path $root 'config\rolling72-enabled.json'))"
}
Write-Host 'END_V4_STORAGE_AUDIT_READ_ONLY'
