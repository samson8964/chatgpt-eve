"""Explicit, one-click V4 full-scan trigger through the EXISTING Windows task.

Never spawn an independent scanner, alter triggers, transmit credentials or
touch V3. Windows Task Scheduler provides IgnoreNew concurrency enforcement.
The command only submits a request: it does NOT prove scan completion.
"""
from __future__ import annotations

import json
import subprocess
import sys

TASK_NAME = "EVE-V4-Shadow"
_TIMEOUT = 15

# Fixed task name; no user-supplied shell syntax or arbitrary command.
_START_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$t = Get-ScheduledTask -TaskName 'EVE-V4-Shadow' -ErrorAction Stop
$state = $t.State.ToString()
if ($state -eq 'Running') {
    [pscustomobject]@{status='ALREADY_RUNNING'} | ConvertTo-Json -Compress
    return
}
if ($state -ne 'Ready') {
    [pscustomobject]@{status='NOT_READY'} | ConvertTo-Json -Compress
    return
}
# Explicitly refuse to start a job whose overlapping-run policy has changed.
# The V4 installer registers this exact setting.
if ($t.Settings.MultipleInstances.ToString() -ne 'IgnoreNew') {
    [pscustomobject]@{status='UNSAFE_MULTIPLE_INSTANCES'} | ConvertTo-Json -Compress
    return
}
Start-ScheduledTask -InputObject $t -ErrorAction Stop
[pscustomobject]@{status='START_REQUESTED'} | ConvertTo-Json -Compress
"""


def request_full_scan(*, runner=subprocess.run, platform=None) -> dict:
    """Submit the installed V4 schedule to start now, without blocking Tk.

    A separate worker thread calls this function. Its result must be processed
    on the Tk GUI thread. Sending the start request DOES NOT imply success,
    receipt of ESI data, or that either research email was delivered.
    """
    if (sys.platform if platform is None else platform) != "win32":
        return {"status": "WINDOWS_REQUIRED"}
    try:
        response = runner(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             _START_SCRIPT],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            timeout=_TIMEOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
        if response.returncode != 0:
            return {"status": "TASK_START_FAILED"}
        data=json.loads(response.stdout.strip())
        if not isinstance(data, dict):
            return {"status": "TASK_START_FAILED"}
        state=data.get("status")
        if state not in ("START_REQUESTED", "ALREADY_RUNNING", "NOT_READY",
                         "UNSAFE_MULTIPLE_INSTANCES"):
            return {"status": "TASK_START_FAILED"}
        return {"status": state}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {"status": "TASK_START_FAILED"}
