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
    # Refuse any third-party or plaintext fallback backend: the credential
    # must remain inside the current Windows user's Credential Manager vault.
    active_backend = keyring.get_keyring()
    if not type(active_backend).__module__.startswith("keyring.backends.Windows"):
        raise RuntimeError("WINDOWS_CREDENTIAL_VAULT_BACKEND_REQUIRED")
    return keyring


def get_bridge_key() -> str | None:
    return _keyring().get_password(SERVICE, getpass.getuser())


def valid_bridge_key(value) -> bool:
    """Only accept printable ASCII keys, 32-256 chars, without outer whitespace.

    Never expose the secret or its precise length in diagnostics.
    """
    return (isinstance(value, str)
            and 32 <= len(value) <= 256
            and value.isascii() and value.isprintable()
            and value == value.strip())


def main():
    p = argparse.ArgumentParser(description="Store an existing bridge key privately")
    opt = p.add_mutually_exclusive_group(required=True)
    opt.add_argument("--set", action="store_true")
    opt.add_argument("--status", action="store_true")
    args = p.parse_args()
    if args.set:
        value = getpass.getpass("Bridge API key (hidden input; use Bitwarden-generated 48 chars): ")
        if not valid_bridge_key(value):
            raise ValueError("INVALID_KEY_INPUT_REQUIRE_32_TO_256_PRINTABLE_ASCII_CHARS")
        _keyring().set_password(SERVICE, getpass.getuser(), value)
    stored = get_bridge_key()
    print(json.dumps({"credential_present": bool(stored),
                      "ready_for_sync": valid_bridge_key(stored),
                      "secret_displayed": False, "mail_enabled": False}))


if __name__ == "__main__":
    main()
