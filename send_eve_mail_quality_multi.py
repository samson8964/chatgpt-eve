from __future__ import annotations

import os
import re
from pathlib import Path

import send_eve_mail_quality as quality
from send_eve_mail_fast import resolve_character


def recipient_names():
    raw = os.getenv("EVE_MAIL_RECIPIENT_NAMES", "").strip()
    if raw:
        names = [x.strip() for x in raw.split(",") if x.strip()]
    else:
        names = [quality.base.RECIPIENT_NAME]
    return list(dict.fromkeys(names))


def safe_recipient_key(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())
    return s.strip("_") or "recipient"


def recipient_top_state_path(name: str) -> Path:
    return Path("results/state") / f"mail_last_top10_{safe_recipient_key(name)}.csv"


def make_spot_push_count_prominent(body: str) -> str:
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
    stamp = quality.pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")

    original_send = quality.base.send_mail
    original_record_history = quality.record_history
    original_top_state_path = quality.TOP_STATE

    # One shared push counter per scan cycle: two recipients do not count as two pushes.
    shared_history = quality.load_history()

    try:
        # Spot channel: suppression state is recipient-specific. A newly added recipient gets
        # the current TOP10 immediately even when an existing recipient already saw it.
        history_before_spot = shared_history.copy()
        spot_history_after_first = None
        for idx, (name, recipient_id) in enumerate(recipients):
            quality.TOP_STATE = recipient_top_state_path(name)
            top_state = quality.load_top_state()

            def send_one(_recipient_id, subject, body, channel_key, *, _name=name, _rid=recipient_id):
                body2 = make_spot_push_count_prominent(body) if channel_key == "spot-deals" else body
                print(f"sending {channel_key} to {_name} ({_rid})")
                original_send(_rid, subject, body2, channel_key)

            quality.base.send_mail = send_one
            # Only the first recipient increments the shared per-contract push counter.
            quality.record_history = original_record_history if idx == 0 else (lambda hist, channel, picked: hist)
            returned_history, _ = quality.send_spot(
                recipient_id,
                stamp,
                history_before_spot.copy(),
                top_state,
            )
            if idx == 0:
                spot_history_after_first = returned_history

        if spot_history_after_first is not None:
            shared_history = spot_history_after_first

        # BPC channel uses the same recipient-specific suppression model and shared counter.
        history_before_bpc = shared_history.copy()
        bpc_history_after_first = None
        for idx, (name, recipient_id) in enumerate(recipients):
            quality.TOP_STATE = recipient_top_state_path(name)
            top_state = quality.load_top_state()

            def send_one_bpc(_recipient_id, subject, body, channel_key, *, _name=name, _rid=recipient_id):
                print(f"sending {channel_key} to {_name} ({_rid})")
                original_send(_rid, subject, body, channel_key)

            quality.base.send_mail = send_one_bpc
            quality.record_history = original_record_history if idx == 0 else (lambda hist, channel, picked: hist)
            returned_history, _ = quality.send_bpc(
                recipient_id,
                stamp,
                history_before_bpc.copy(),
                top_state,
            )
            if idx == 0:
                bpc_history_after_first = returned_history

        if bpc_history_after_first is not None:
            shared_history = bpc_history_after_first

        # Persist the shared counter even if only the second recipient needed a first-time send.
        quality.HISTORY.parent.mkdir(parents=True, exist_ok=True)
        shared_history.to_csv(quality.HISTORY, index=False)
    finally:
        quality.base.send_mail = original_send
        quality.record_history = original_record_history
        quality.TOP_STATE = original_top_state_path


if __name__ == "__main__":
    main()
