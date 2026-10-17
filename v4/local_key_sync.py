"""Coordinate EVE bridge key rotation without placing the key on the command line.

IMPORTANT: first generate and save a strong replacement in Bitwarden. Use
v4.local_bridge_auth --set to store the same value in Windows Credential
Manager. This tool reads the vault and uploads the identical value through
GitHub CLI stdin; it never displays or logs the value.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess

REPO = "samson8964/chatgpt-eve"
DEPLOY_REF = "prep/v4-windows-local-migration-20261013"
WORKFLOW = "deploy-cloudflare-worker.yml"


def _gh(args: list[str], *, secret: str | None = None, runner=subprocess.run) -> None:
    # Do not include secrets in argv, errors, logs, exception repr, or files.
    cmd = ["gh", *args]
    kwargs = {"text": True, "capture_output": True, "check": False, "timeout": 120}
    if secret is not None:
        kwargs["input"] = secret
    else:
        kwargs["input"] = ""
    try:
        result = runner(cmd, **kwargs)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("GITHUB_CLI_COMMAND_FAILED:" + type(exc).__name__) from None
    if result.returncode:
        raise RuntimeError("GITHUB_CLI_EXIT_NONZERO; check gh auth status and repo permissions")


def sync_github(*, get_key=None, runner=subprocess.run) -> dict:
    if get_key is None:
        from v4.local_bridge_auth import get_bridge_key
        get_key = get_bridge_key
    from v4.local_bridge_auth import valid_bridge_key
    key = get_key()
    if not valid_bridge_key(key):
        raise RuntimeError("VAULT_KEY_MISSING_OR_WEAK; save a Bitwarden generated 48-char key first")
    if shutil.which("gh") is None and runner is subprocess.run:
        raise RuntimeError("GH_CLI_NOT_INSTALLED")
    _gh(["auth", "status", "-h", "github.com"], runner=runner)
    _gh(["secret", "set", "EVE_MAIL_API_KEY", "--repo", REPO,
         "--app", "actions"], secret=key, runner=runner)
    return {"github_secret_updated": True, "github_secret_name":"EVE_MAIL_API_KEY",
            "bitwarden_saved": "USER_MUST_CONFIRM", "cloudflare_updated": False,
            "email_sent": False, "secret_printed": False}


def deploy_worker(*, runner=subprocess.run) -> dict:
    if shutil.which("gh") is None and runner is subprocess.run:
        raise RuntimeError("GH_CLI_NOT_INSTALLED")
    _gh(["auth", "status", "-h", "github.com"], runner=runner)
    _gh(["workflow", "run", WORKFLOW, "--repo", REPO,
         "--ref", DEPLOY_REF], runner=runner)
    return {"deployment_queued":True,"worker":"eve-contract-opener",
            "worker_syncs_mail_api_key":True,"code_ref":DEPLOY_REF,
            "email_sent":False,"secret_printed":False,
            "verified_access":False,
            "next_step":"Inspect GitHub deploy workflow result, then local_bridge_probe"}


def main():
    p=argparse.ArgumentParser(description="EVE bridge key GitHub sync and safe deployment")
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sync-github",action="store_true")
    mode.add_argument("--deploy-worker",action="store_true")
    args=p.parse_args()
    result=sync_github() if args.sync_github else deploy_worker()
    print(json.dumps(result,indent=2,ensure_ascii=False))


if __name__ == "__main__":
    main()
