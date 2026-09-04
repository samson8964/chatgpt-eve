from __future__ import annotations

import os
import re

import send_eve_mail_quality as quality
from send_eve_mail_fast import resolve_character


def recipient_names():
    raw = os.getenv("EVE_MAIL_RECIPIENT_NAMES", "").strip()
    if raw:
        names = [x.strip() for x in raw.split(",") if x.strip()]
    else:
        names = [quality.base.RECIPIENT_NAME]
    # Preserve order while removing duplicates.
    return list(dict.fromkeys(names))


def make_spot_push_count_prominent(body: str) -> str:
    """Render the per-contract push count on its own line in spot mail."""
    pattern = r"(<b>【现货-[^】]+】) · 已推送次数：(\d+)</b><br>"
    return re.sub(
        pattern,
        lambda m: f"{m.group(1)}</b><br><b>推送记录：第 {m.group(2)} 次</b><br>",
        body,
    )


def main():
    if not quality.base.API_KEY:
        raise RuntimeError("Missing EVE_MAIL_API_KEY")

    names = recipient_names()
    recipients = [(name, resolve_character(name)) for name in names]
    original_send = quality.base.send_mail

    def broadcast(_recipient_id, subject, body, channel_key):
        if channel_key == "spot-deals":
            body = make_spot_push_count_prominent(body)
        for name, recipient_id in recipients:
            print(f"sending {channel_key} to {name} ({recipient_id})")
            original_send(recipient_id, subject, body, channel_key)

    quality.base.send_mail = broadcast
    quality.main()


if __name__ == "__main__":
    main()
