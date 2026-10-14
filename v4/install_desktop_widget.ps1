# Create a Windows Desktop shortcut for the EVE V4 shadow read-only monitor.
# Does not register/change the scanner schedule, access credentials, or enable mail.
param(
    [string]$DataRoot = (Join-Path $HOME 'EVE-V4-Data'),
    [switch]$AutoStart,
    [switch]$NoLaunch
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonw = Join-Path $repo '.venv\Scripts\pythonw.exe'
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonw -PathType Leaf) -or
    -not (Test-Path $python -PathType Leaf)) {
    throw 'Python virtual environment missing windowed or console interpreter.'
}
if (-not (Test-Path (Join-Path $repo 'v4\desktop_widget.py') -PathType Leaf)) {
    throw 'V4 widget program is missing.'
}
# Quick local import preflight. Never connect to cloud or Windows vault.
Push-Location $repo
try {
    & $python -c "import tkinter; import v4.desktop_widget; print('WIDGET_IMPORT_OK')"
    if ($LASTEXITCODE -ne 0) { throw 'Tkinter or widget import failed.' }
} finally {
    Pop-Location
}
$desktop = [Environment]::GetFolderPath('Desktop')
if (-not $desktop -or -not (Test-Path $desktop)) {
    throw 'Windows desktop folder could not be resolved.'
}
$name = 'EVE V4 Monitor.lnk'
$args = '-m v4.desktop_widget --data-root "' + $DataRoot + '"'
$shell = New-Object -ComObject WScript.Shell
$shortcutPath = Join-Path $desktop $name

function Write-EveWidgetShortcut([string]$Destination) {
    $link = $shell.CreateShortcut($Destination)
    $link.TargetPath = $pythonw
    $link.Arguments = $args
    $link.WorkingDirectory = $repo
    $link.Description = 'EVE V4 read-only local shadow monitor (no scans or mail)'
    $link.IconLocation = (Join-Path $env:WINDIR 'System32\shell32.dll') + ',21'
    $link.Save()
}

Write-EveWidgetShortcut -Destination $shortcutPath
Write-Host ('Desktop shortcut created: ' + $shortcutPath)
Write-Host 'Read-only UI: local Task Scheduler + log + scan manifest; no secrets or mail.'

if ($AutoStart) {
    $startup = [Environment]::GetFolderPath('Startup')
    if (-not $startup) { throw 'Windows Startup folder could not be resolved.' }
    $startupPath = Join-Path $startup $name
    Write-EveWidgetShortcut -Destination $startupPath
    Write-Host ('Starts at next Windows login: ' + $startupPath)
}
if (-not $NoLaunch) {
    # Clicking the installed shortcut starts only the UI via pythonw (no CMD).
    Start-Process -FilePath $shortcutPath
    Write-Host 'Widget launch requested.'
}
