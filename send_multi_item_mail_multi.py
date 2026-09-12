from __future__ import annotations

import os
import re
import time
from pathlib import Path

import requests

import send_multi_item_mail as multi


def recipient_names():
    raw = os.getenv("EVE_MAIL_RECIPIENT_NAMES", "").strip()
    if raw:
        names = [x.strip() for x in raw.split(",") if x.strip()]
    else:
        names = [multi.base.RECIPIENT_NAME]
    return list(dict.fromkeys(names))


def safe_recipient_key(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())
    return s.strip("_") or "recipient"


def recipient_state_path(name: str) -> Path:
    return Path("results/state") / f"mail_last_multi_top10_{safe_recipient_key(name)}.csv"


def main():
    if not multi.base.API_KEY:
        raise RuntimeError("Missing EVE_MAIL_API_KEY")

    names = recipient_names()
    primary_name = (os.getenv("EVE_MAIL_RECIPIENT_NAME", "").strip() or names[0])
    original_send = multi.base.send_mail
    original_name = multi.base.RECIPIENT_NAME
    original_state = multi.STATE
    failures = []

    try:
        for name in names:
            multi.base.RECIPIENT_NAME = name
            multi.STATE = recipient_state_path(name)

            def send_with_retry(recipient_id, subject, body, channel_key, *, _name=name):
                # Retry only explicit upstream 5xx HTTP responses. Connection-loss / unknown-result
                # failures are not retried automatically because the EVE mail may already exist.
                for attempt in range(1, 4):
                    try:
                        print(f"sending {channel_key} to {_name} ({recipient_id}) attempt={attempt}")
                        return original_send(recipient_id, subject, body, channel_key)
                    except requests.exceptions.HTTPError as exc:
                        status = exc.response.status_code if exc.response is not None else 0
                        if status < 500 or attempt >= 3:
                            raise
                        delay = 2 * attempt
                        print(f"mail upstream HTTP {status}; retry {_name} in {delay}s")
                        time.sleep(delay)

            multi.base.send_mail = send_with_retry
            try:
                multi.main()
            except Exception as exc:
                failures.append((name, exc))
                print(f"::warning::multi-item mail failed for {name}: {type(exc).__name__}: {exc}")
    finally:
        multi.base.send_mail = original_send
        multi.base.RECIPIENT_NAME = original_name
        multi.STATE = original_state

    primary_failure = next((exc for name, exc in failures if name.casefold() == primary_name.casefold()), None)
    if primary_failure is not None:
        raise RuntimeError(f"Primary multi-item recipient {primary_name} mail failed") from primary_failure
    if failures:
        print("multi-item secondary recipient failures did not invalidate the completed scan/results")


if __name__ == "__main__":
    main()
