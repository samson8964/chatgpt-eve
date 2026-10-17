# EVE V4 Windows desktop mini monitor

Status: read-only utility on isolated V4 Windows migration branch; not a scan
scheduler, trading tool, or mail sender.

## Installation

From an ordinary Windows PowerShell session under the same Windows account
that registered `EVE-V4-Shadow`:

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path (Get-Location) 'v4\install_desktop_widget.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Shortcut creation failed' }
```

Creates `EVE V4 Monitor.lnk` in the actual Windows desktop folder and launches
the widget using `.venv\Scripts\pythonw.exe` (no terminal).
No admin rights, new dependencies, cloud APIs, or changes to the existing
scheduled task are required. Clicking the shortcut re-opens the widget after
it is closed.

Option: add `-AutoStart` to the installer to also create the user's Startup
folder shortcut, so the monitor opens at the next sign-in. The scanner
already runs via Task Scheduler; this Startup link starts **only the visual
monitor**. To remove the monitor, close its `×` and delete the Desktop and/or
Startup shortcut. Neither action disables the scanner.

## UI behaviour

- Small (~358×255) dark frameless window near the top right. Drag by its top
  bar, toggle always-on-top with the pin button, close with `×`.
- Read only from `EVE-V4-Data\logs\shadow-task.log`, small scan manifests,
  and the latest completed `deep_shadow.json`. Reads do not mutate SQLite.
- Local phase/status and log refresh **every 3 seconds**; Windows Task Scheduler
  status poll **about every 12 seconds** on a background thread; snapshots
  and last-run details may lag the underlying scan briefly. No invented %
  complete, ETA, activity, trades or live API status.
- Shows Running/Ready/Disabled/missing task, scan phase (full market, deep
  scan, audit), latest result including partial/quarantine/failure, per-building
  last-completed coverage, previous run's proof and model candidate counts,
  and next scheduled run. Values are **from the latest completed run**, not
  predictions of current run progress.
- Windows Task Scheduler polling is windowless PowerShell
  `Get-ScheduledTask` + `Get-ScheduledTaskInfo`, using the signed-in user.
- `查看日志` opens the existing text log through Windows. It never launches
  the scanner, requests ESI, reads Windows Credential Manager, creates API
  requests, or sends mail. The UI explicitly says `MAIL OFF`.
- Single-instance Windows mutex prevents duplicate windows. If the widget
  shows "Task missing", confirm it runs under the same Windows account as the
  scheduled task.

## Validation and limitations

`python -m unittest discover -s v4/tests -v` includes offline fixture
tests for latest status, newest running phase, failed previous attempt,
Task Scheduler command invocation, shortcut install PowerShell parser, and
safety properties. These automated tests are **not** proof that the GUI has
visibly launched on the user's machine. That requires the Windows shortcut
to be run and observed locally.

The monitor displays previous stored scan health; it does not assert
unverified orders are executable or that formal opportunity emails are enabled.
