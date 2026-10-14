"""Windows user credential access for EVE V4 shadow scans; no secret is printed."""
from __future__ import annotations

import argparse
import getpass
import json
import sys

SERVICE = "eve-v4-structure-market-bridge"


def _keyring():
    if sys.platform != "win32":
        raise RuntimeError("WINDOWS_ONLY")
    import keyring
    return keyring


def get_bridge_key() -> str | None:
    return _keyring().get_password(SERVICE, getpass.getuser())


def main():
    p = argparse.ArgumentParser(description="Store an existing bridge key privately")
    opt = p.add_mutually_exclusive_group(required=True)
    opt.add_argument("--set", action="store_true")
    opt.add_argument("--status", action="store_true")
    args = p.parse_args()
    if args.set:
        value = getpass.getpass("Existing bridge API key (hidden input): ")
        if not value or value != value.strip():
            raise ValueError("INVALID_KEY_INPUT")
        _keyring().set_password(SERVICE, getpass.getuser(), value)
    print(json.dumps({"credential_present":bool(get_bridge_key()),
                      "secret_displayed":False,"mail_enabled":False}))


if __name__ == "__main__":
    main()
