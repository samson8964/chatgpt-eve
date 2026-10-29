<# Safe single-run V4 audit. READ-ONLY: no mail, cleanup, task mutation or database writes. #>
[CmdletBinding()]
param([string]$DataRoot='C:\Users\mike\EVE-V4-Data')
$ErrorActionPreference='Stop'
$root=[System.IO.Path]::GetFullPath($DataRoot)
function H([string]$name){Write-Host ([Environment]::NewLine+'=== '+$name+' ===')}
function ReadTask([string]$name){
 try{
  $task=Get-ScheduledTask -TaskName $name -ErrorAction Stop
  $info=Get-ScheduledTaskInfo -TaskName $name -ErrorAction Stop
  [pscustomobject]@{Task=$name;State=[string]$task.State;LastRun=$info.LastRunTime;NextRun=$info.NextRunTime;LastCode=$info.LastTaskResult}
 }catch{[pscustomobject]@{Task=$name;State='NOT_FOUND';LastRun=$null;NextRun=$null;LastCode=$null}}
}
function GetMarker($lines,[string]$prefix){
 $line=$lines | Where-Object {$_.StartsWith($prefix+' ')} | Select-Object -Last 1
 if(-not $line){return $null}
 try{$line.Substring($prefix.Length+1)|ConvertFrom-Json -ErrorAction Stop}catch{return $null}
}
H '1 TASKS'
$tasks=@((ReadTask 'EVE-V4-Shadow'),(ReadTask 'EVE-V4-Daily-Backup'),(ReadTask 'EVE-V4-Opportunity-Push'))
$tasks|Format-Table -AutoSize
H '2 LAST SCAN CYCLE'
$log=Join-Path $root 'logs\shadow-task.log'
$lines=@()
if(Test-Path -LiteralPath $log){$lines=@(Get-Content -LiteralPath $log -Encoding UTF8 -Tail 800)}
$idx=-1
for($i=0;$i -lt $lines.Count;$i++){if($lines[$i].StartsWith('START ')){$idx=$i}}
$cycle=@()
if($idx -ge 0){$cycle=@($lines[$idx..($lines.Count-1)])}
if($cycle.Count){Write-Host $cycle[0]}else{Write-Host 'NO_START_RECORD'}
foreach($marker in @('full_scan: starting','full_scan: completed','deep_scan: starting','deep_scan: completed','sqlite_persist: starting','sqlite_persist: completed','FAILED ','REVIEW_MAIL_FAILED ','GAME_REVIEW_MAIL_FAILED ')){
 $matches=@($cycle|Where-Object {$_.StartsWith($marker)})
 if($matches.Count){Write-Host ($matches[-1].Substring(0,[math]::Min(220,$matches[-1].Length)))}
}
$res=GetMarker $cycle 'RESULT'
$gmail=GetMarker $cycle 'REVIEW_MAIL'
$game=GetMarker $cycle 'GAME_REVIEW_MAIL'
$rolling=GetMarker $cycle 'ROLLING72_CLEANUP'
$hot=GetMarker $cycle 'HOT_PROOF_RETENTION'
$gov=GetMarker $cycle 'STORAGE_GOVERNOR'
if($res){Write-Host "SCAN_RESULT: $($res.status); run=$($res.run_folder_name); backup=$($res.backup)"}else{Write-Host 'SCAN_RESULT: NOT_YET_LOGGED'}
if($gmail){Write-Host "GMAIL_RESULT: $($gmail.status); sent=$($gmail.sent); run=$($gmail.run_folder_name)"}else{Write-Host 'GMAIL_RESULT: NOT_YET_LOGGED'}
if($game){
 Write-Host "GAME_RESULT: $($game.status); success=$($game.recipient_success_count); failure=$($game.recipient_failure_count)"
 if($game.recipients){
  foreach($p in $game.recipients.PSObject.Properties){
   Write-Host "GAME_RECIPIENT: $($p.Name); status=$($p.Value.status); mail_id=$($p.Value.mail_id); error=$($p.Value.error_code)"
  }
 }
}else{Write-Host 'GAME_RESULT: NOT_YET_LOGGED'}
if($hot){Write-Host "HOT_RETENTION: $($hot.status)"}
if($rolling){Write-Host "ROLLING72: $($rolling.status); deleted=$($rolling.deleted); blocked=$($rolling.blocked); freed_bytes=$($rolling.reclaimed_bytes)"}
if($gov){Write-Host "STORAGE_GOVERNOR: severity=$($gov.severity); free_gib=$($gov.free_gib)"}
if($tasks[0].State -eq 'Running'){
 if($res -and $game -and -not $rolling){Write-Host 'LIKELY_STAGE: post-game mail, before rolling72 conclusion'}
 elseif($res -and $rolling -and -not $gov){Write-Host 'LIKELY_STAGE: storage governor after cleanup'}
 elseif($res -and $gmail -and -not $game){Write-Host 'LIKELY_STAGE: game mail processing'}
 elseif(-not $res){Write-Host 'LIKELY_STAGE: scanning or persisting'}
 else{Write-Host 'LIKELY_STAGE: check subsequent task result and maintenance'}
}
H '3 GAME RECEIPTS'
if($res -and $res.run_folder_name){
 $folder=Join-Path $root 'mail-review\eve-receipts'
 $receipts=@(Get-ChildItem -LiteralPath $folder -Filter ($res.run_folder_name+'*.json') -File -ErrorAction SilentlyContinue)
 if(-not $receipts.Count){Write-Host 'NO_LOCAL_GAME_RECEIPTS_FOR_THIS_RUN'}
 foreach($f in $receipts){
  try{
   $receipt=Get-Content -LiteralPath $f.FullName -Encoding UTF8 -Raw|ConvertFrom-Json
   Write-Host "RECEIPT: recipient=$($receipt.recipient); mail_id=$($receipt.mail_id); confirmed=$($receipt.confirmed_at); duplicate=$($receipt.already_accepted)"
  }catch{Write-Host "UNREADABLE_RECEIPT: $($f.Name)"}
 }
}else{Write-Host 'NO_COMPLETED_RUN'}
H '4 SEPARATE FORMAL OPPORTUNITY REPORT'
Write-Host "FORMAL_TASK: $($tasks[2].State)"
$opDir=Join-Path $root 'opportunity-push'
$latest=Get-ChildItem -LiteralPath $opDir -Filter '*.json' -File -ErrorAction SilentlyContinue|Where-Object {$_.Name -ne 'state.json'}|Sort-Object LastWriteTime -Descending|Select-Object -First 1
if($latest){
 try{
  $o=Get-Content -LiteralPath $latest.FullName -Encoding UTF8 -Raw|ConvertFrom-Json
  Write-Host "FORMAL_REPORT: status=$($o.status); finished=$($o.finished_at); modified=$($latest.LastWriteTime)"
 }catch{Write-Host "FORMAL_REPORT: invalid JSON, file=$($latest.Name)"}
}else{Write-Host 'FORMAL_REPORT: NOT_FOUND'}
if($tasks[2].State -eq 'Disabled'){Write-Host 'NOTE: formal report stays stale while the independent opportunity task remains disabled'}
H '5 PYTHON PROCESS ACTIVITY IN 8 SEC'
$before=@{}
$ps=@(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue)
foreach($item in $ps){
 $p=Get-Process -Id $item.ProcessId -ErrorAction SilentlyContinue
 if($p){$before[[int]$item.ProcessId]=@{Cpu=[double]$p.CPU;Read=[double]$item.ReadTransferCount;Write=[double]$item.WriteTransferCount}}
}
Start-Sleep -Seconds 8
$rows=@()
foreach($item in $ps){
 $curr=Get-CimInstance Win32_Process -Filter "ProcessId=$($item.ProcessId)" -ErrorAction SilentlyContinue
 $p=Get-Process -Id $item.ProcessId -ErrorAction SilentlyContinue
 $b=$before[[int]$item.ProcessId]
 if($curr -and $p -and $b){
  $mod='child/other'
  if(([string]$item.CommandLine) -match '-m\s+(v4\.[A-Za-z0-9_]+)'){$mod=$Matches[1]}
  $rows+=[pscustomobject]@{PID=$item.ProcessId;Parent=$item.ParentProcessId;Module=$mod;Cpu8s=[math]::Round([double]$p.CPU-$b.Cpu,2);ReadMB=[math]::Round(([double]$curr.ReadTransferCount-$b.Read)/1MB,2);WriteMB=[math]::Round(([double]$curr.WriteTransferCount-$b.Write)/1MB,2)}
 }
}
$rows|Format-Table -AutoSize
H '6 DATABASE AND BACKUP'
$db=Join-Path $root 'sqlite\v4-shadow.sqlite3'
foreach($path in @($db,($db+'-wal'),($db+'-shm'))){
 if(Test-Path -LiteralPath $path){
  $f=Get-Item -LiteralPath $path
  Write-Host "DB_FILE: name=$($f.Name); GiB=$([math]::Round($f.Length/1GB,3)); modified=$($f.LastWriteTime)"
 }
}
$rot=Join-Path $root 'logs\manual-retention.log'
if(Test-Path -LiteralPath $rot){Get-Content -LiteralPath $rot -Tail 10|ForEach-Object {Write-Host ('BACKUP: '+$_)}}
$err=Join-Path $root 'logs\manual-retention.err.log'
if(Test-Path -LiteralPath $err){Get-Content -LiteralPath $err -Tail 5|ForEach-Object {Write-Host ('BACKUP_ERROR: '+$_)}}
$count=@(Get-ChildItem -LiteralPath (Join-Path $root 'backups') -Filter 'v4-shadow-*.sqlite3' -File -ErrorAction SilentlyContinue).Count
Write-Host "LOCAL_BACKUPS: $count"
Write-Host "ROLLING72_CONFIG_EXISTS: $(Test-Path -LiteralPath (Join-Path $root 'config\rolling72-enabled.json'))"
Write-Host "C_FREE_GIB: $([math]::Round((Get-PSDrive C).Free/1GB,2))"
Write-Host 'END_READ_ONLY_AUDIT'
