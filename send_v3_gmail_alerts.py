from __future__ import annotations

import html
import os
import re
import smtplib
import time
from email.message import EmailMessage
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from send_v3_opportunity_mail import CHANNELS, build_candidates, enabled_channels, render
from v3_market_alert_state import acknowledge as acknowledge_market, plan as plan_market
from v3_scan_health import channel_healthy

STATE = Path("results/state")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_USER = os.getenv("GMAIL_SMTP_USER", "").strip()
APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
RECIPIENT = os.getenv("GMAIL_TO", "").strip() or SMTP_USER


def state_path(channel: str) -> Path:
    return STATE / f"gmail_seen_{channel}.csv"


def _read_ids(path: Path) -> set[int]:
    if not path.exists():
        return set()
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return set()
    if "id" not in df.columns:
        return set()
    return set(pd.to_numeric(df["id"], errors="coerce").dropna().astype("int64").tolist())


def _save_ids(path: Path, ids: set[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    now = pd.Timestamp.now(tz="UTC").isoformat()
    rows = [{"id": int(x), "recorded_at": now} for x in sorted(ids)]
    pd.DataFrame(rows, columns=["id", "recorded_at"]).to_csv(path, index=False)


def _previous_v3_mail_ids(channel: str) -> set[int]:
    ids: set[int] = set()
    for path in STATE.glob(f"mail_last_{channel}_*.csv"):
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if "id" in df.columns:
            ids.update(pd.to_numeric(df["id"], errors="coerce").dropna().astype("int64").tolist())
    return ids


def _eve_to_plain(body: str) -> str:
    s = body.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    s = re.sub(r"<url=[^>]+>", "", s, flags=re.I)
    s = re.sub(r"</url>", "", s, flags=re.I)
    s = re.sub(r"</?b>", "", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def _eve_to_html(body: str) -> str:
    s = body
    s = re.sub(r"<url=contract:0//(\d+)>", r'<a href="https://eve-contract-opener.99617224.workers.dev/c/\1">', s, flags=re.I)
    s = re.sub(r"<url=showinfo:(\d+)>", r'<a href="https://eve-contract-opener.99617224.workers.dev/m/\1">', s, flags=re.I)
    s = re.sub(r"<url=[^>]+>", "", s, flags=re.I)
    s = re.sub(r"</url>", "</a>", s, flags=re.I)
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:760px;'
        'margin:auto;color:#1f2937;line-height:1.55">'
        + s
        + "</div>"
    )


def _send(subject: str, plain: str, html_body: str) -> None:
    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = RECIPIENT
    msg["Subject"] = subject
    msg.set_content(plain)
    msg.add_alternative(html_body, subtype="html")

    last = None
    for attempt in range(1, 4):
        try:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
                smtp.login(SMTP_USER, APP_PASSWORD)
                smtp.send_message(msg)
            print(f"v3 gmail sent to {RECIPIENT} attempt={attempt}")
            return
        except Exception as exc:
            last = exc
            if attempt >= 3:
                break
            time.sleep(2 * attempt)
    raise RuntimeError(f"V3 Gmail delivery failed: {type(last).__name__}: {last}")


def main() -> None:
    if not SMTP_USER or not APP_PASSWORD:
        print("V3 Gmail disabled: missing GMAIL_SMTP_USER or GMAIL_APP_PASSWORD")
        return

    stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")
    failures = []

    for channel in enabled_channels():
        kind = CHANNELS[channel]["kind"]
        is_market = kind in {"source-market", "reverse-market"}
        if is_market and not channel_healthy(channel, require_manifest=True):
            print(f"::warning::{channel}: skip Gmail and preserve dedupe state: scan missing, failed or stale")
            continue

        candidates = build_candidates(channel)
        if is_market:
            market_path = STATE / f"gmail_market_state_{channel}.csv"
            now = datetime.now(timezone.utc)
            pending = plan_market(
                market_path, candidates, now=now,
                cooldown_hours=float(os.getenv("V3_MARKET_GMAIL_COOLDOWN_HOURS", "6")),
            )
            print(f"{channel}: Gmail market eligible={len(candidates)} pending={len(pending)}")
            for candidate in pending:
                ident = int(candidate["id"])
                subject, body = render(channel, stamp, [candidate])
                try:
                    _send(f"【EVE捡漏】{subject}", _eve_to_plain(body), _eve_to_html(body))
                    acknowledge_market(market_path, candidate, now=datetime.now(timezone.utc))
                except Exception as exc:
                    failures.append((channel, ident, exc))
                    print(f"::warning::Gmail market alert failed {channel}:{ident}: {type(exc).__name__}: {exc}")
            continue

        path = state_path(channel)
        current_ids = {int(c["id"]) for c in candidates}

        # First configured run establishes a no-backfill baseline. It also absorbs
        # the currently persisted V3 EVE-mail state, so opportunities already sent
        # before Gmail was enabled are not mailed again.
        if not path.exists():
            baseline = current_ids | _previous_v3_mail_ids(channel)
            _save_ids(path, baseline)
            print(f"{channel}: Gmail baseline initialized with {len(baseline)} ids; no stock mail")
            continue

        seen = _read_ids(path)
        fresh = [c for c in candidates if int(c["id"]) not in seen]
        print(f"{channel}: Gmail new={len(fresh)} current={len(candidates)}")

        for candidate in fresh:
            ident = int(candidate["id"])
            subject, body = render(channel, stamp, [candidate])
            gmail_subject = f"【EVE捡漏】{subject}"
            try:
                _send(gmail_subject, _eve_to_plain(body), _eve_to_html(body))
                seen.add(ident)
                _save_ids(path, seen)
            except Exception as exc:
                failures.append((channel, ident, exc))
                print(f"::warning::Gmail alert failed {channel}:{ident}: {type(exc).__name__}: {exc}")

    if failures:
        raise RuntimeError(f"V3 Gmail alert delivery failed for {len(failures)} new opportunity(s)")


if __name__ == "__main__":
    main()
