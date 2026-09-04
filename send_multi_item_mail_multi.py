from __future__ import annotations

import os

import send_multi_item_mail as multi
from send_eve_mail_fast import resolve_character


def recipient_names():
    raw = os.getenv("EVE_MAIL_RECIPIENT_NAMES", "").strip()
    if raw:
        names = [x.strip() for x in raw.split(",") if x.strip()]
    else:
        names = [multi.base.RECIPIENT_NAME]
    return list(dict.fromkeys(names))


def main():
    if not multi.base.API_KEY:
        raise RuntimeError("Missing EVE_MAIL_API_KEY")

    names = recipient_names()
    recipients = [(name, resolve_character(name)) for name in names]
    original_send = multi.base.send_mail

    def broadcast(_recipient_id, subject, body, channel_key):
        for name, recipient_id in recipients:
            print(f"sending {channel_key} to {name} ({recipient_id})")
            original_send(recipient_id, subject, body, channel_key)

    multi.base.send_mail = broadcast
    multi.main()


if __name__ == "__main__":
    main()
