# EVE V4 Desktop Monitor: fourth-station upgrade

Branch: prep/v4-windows-local-migration-20261013

## Added
- Four private station indicators: 4-H, C-J, O4T and 74L2-U.
- 74L2-U is shown as OFF unless the existing exact local opt-in flag is valid.
- Green four-station result requires a newly recorded complete scan after the opt-in flag was written.
- Previous three-station success can never masquerade as successful four-station coverage.
- Real read-only summaries from the existing opportunity-push/*.json receipts:
  last valid hourly opportunity cycle, candidate count, 74L2-U sell types,
  Jita depth prefilter pass count, model pass count, and independent EVE/Gmail delivery statuses.
- Successful opportunity reports older than three hours are marked STALE;
  a malformed latest report does not fall back to an older green report.
- A newer failed shadow run cannot display older green four-station statuses.
- No ESI queries, OAuth calls, mail-sends, local background process or new task is added by the widget.
- Existing manual scan button continues to request ONLY the existing Windows Task Scheduler job.

## Upgrade (Windows PowerShell, safe: no task/SSO/Worker changes)
    $repo = Join-Path $HOME 'EVE-V4-Code'
    git -C $repo pull --ff-only
    if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }
    Set-Location $repo
    & .\.venv\Scripts\python.exe -m unittest v4.tests.test_desktop_monitor v4.tests.test_desktop_four_station v4.tests.test_desktop_shortcut
    if ($LASTEXITCODE -ne 0) { throw 'Widget regression tests failed' }

Close the existing monitor via its X button and reopen the existing
'EVE V4 Monitor' desktop shortcut. The original Windows shortcut
runs the .venv pythonw.exe from this repository and does not need reinstall.
Because the monitor is single-instance, double-clicking while an older
monitor window is still running will not replace it.

Optional preflight snapshot (read only, no tkinter window):
    & .\.venv\Scripts\python.exe -c 'from v4.desktop_status import read_snapshot; from pathlib import Path; import json; s=read_snapshot(Path.home()/"EVE-V4-Data"); print(json.dumps({k:s[k] for k in ("banestar_enabled","scan_scope_status","structures","opportunity")},ensure_ascii=False,indent=2))'

## Evidence boundary
Manual BANESTAR full-pagination canary succeeding does not prove a scheduled
four-station shadow scan or hourly notification completed. Display stays
pending until persisted new production-run evidence is available.
All market opportunities are research estimates, not guaranteed live trades.
Worker deployment is not required for this UI-only update.
