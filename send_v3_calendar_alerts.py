from __future__ import annotations

import hashlib
import html as html_lib
import json
import os
import re
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

from send_v3_opportunity_mail import CHANNELS, build_candidates, enabled_channels, render

STATE = Path("results/state")
SCOPE = "https://www.googleapis.com/auth/calendar.events"
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "").strip()
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_CALENDAR_SERVICE_ACCOUNT_JSON", "").strip()
TIMEZONE = os.getenv("GOOGLE_CALENDAR_TIMEZONE", "Asia/Shanghai").strip() or "Asia/Shanghai"


def state_path(channel: str) -> Path:
    return STATE / f"calendar_seen_{channel}.csv"


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


def _previous_mail_ids(channel: str) -> set[int]:
    ids: set[int] = set()
    for path in STATE.glob(f"mail_last_{channel}_*.csv"):
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if "id" in df.columns:
            ids.update(pd.to_numeric(df["id"], errors="coerce").dropna().astype("int64").tolist())
    return ids


def _save_ids(path: Path, ids: set[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"id": int(x)} for x in sorted(ids)]
    pd.DataFrame(rows, columns=["id"]).to_csv(path, index=False)


def _plain(body: str) -> str:
    s = body.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    s = re.sub(r"<url=[^>]+>", "", s, flags=re.I)
    s = re.sub(r"</url>", "", s, flags=re.I)
    s = re.sub(r"</?b>", "", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return html_lib.unescape(s).strip()


def _event_id(channel: str, ident: int) -> str:
    key = f"{channel}:{int(ident)}".encode("utf-8")
    return "eve" + hashlib.sha256(key).hexdigest()[:29]


def _session() -> AuthorizedSession:
    info = json.loads(SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(info, scopes=[SCOPE])
    return AuthorizedSession(creds)


def _insert_event(session: AuthorizedSession, channel: str, candidate: dict, stamp: str) -> bool:
    ident = int(candidate["id"])
    subject, body = render(channel, stamp, [candidate])
    now = pd.Timestamp.now(tz=TIMEZONE)
    start = now + pd.Timedelta(minutes=1)
    end = start + pd.Timedelta(minutes=15)
    event = {
        "id": _event_id(channel, ident),
        "summary": subject,
        "description": _plain(body),
        "start": {"dateTime": start.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end.isoformat(), "timeZone": TIMEZONE},
        "transparency": "transparent",
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 0}],
        },
        "extendedProperties": {
            "private": {
                "eveOpportunityChannel": channel,
                "eveOpportunityId": str(ident),
            }
        },
    }
    url = f"https://www.googleapis.com/calendar/v3/calendars/{quote(CALENDAR_ID, safe='')}/events"
    resp = session.post(url, json=event, timeout=30)
    if resp.status_code in (200, 201):
        print(f"calendar created: {channel}:{ident}")
        return True
    if resp.status_code == 409:
        print(f"calendar duplicate already exists: {channel}:{ident}")
        return True
    raise requests.HTTPError(
        f"Calendar insert failed {resp.status_code}: {resp.text[:500]}",
        response=resp,
    )


def main() -> None:
    if not SERVICE_ACCOUNT_JSON or not CALENDAR_ID:
        print("Google Calendar alerts disabled: missing GOOGLE_CALENDAR_SERVICE_ACCOUNT_JSON or GOOGLE_CALENDAR_ID")
        return

    session = _session()
    stamp = pd.Timestamp.now(tz=TIMEZONE).strftime("%m-%d %H:%M")
    failures = []

    for channel in enabled_channels():
        if channel not in CHANNELS:
            continue
        path = state_path(channel)
        first_activation = not path.exists()
        seen = _read_ids(path)

        # On the first activation only, seed the calendar dedupe state from the
        # previous V3 EVE-mail state. This prevents already-mailed opportunities
        # from being backfilled into Google Calendar.
        if first_activation:
            seeded = _previous_mail_ids(channel)
            if seeded:
                print(f"{channel}: seed {len(seeded)} previously mailed ids into calendar dedupe")
                seen.update(seeded)
            _save_ids(path, seen)

        candidates = build_candidates(channel)
        fresh = [c for c in candidates if int(c["id"]) not in seen]
        print(f"{channel}: calendar fresh={len(fresh)} current={len(candidates)}")
        for c in fresh:
            try:
                if _insert_event(session, channel, c, stamp):
                    seen.add(int(c["id"]))
                    _save_ids(path, seen)
            except Exception as exc:
                failures.append((channel, int(c["id"]), exc))
                print(f"::warning::calendar alert failed {channel}:{c['id']}: {type(exc).__name__}: {exc}")

    if failures:
        raise RuntimeError(f"Google Calendar alert delivery failed for {len(failures)} opportunity(s)")


if __name__ == "__main__":
    main()
