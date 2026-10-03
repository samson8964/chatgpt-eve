#!/usr/bin/env python3
"""Minimal public EVE Freelance Jobs scanner.

Phase 1 intentionally does not authenticate or accept jobs.
It fetches the public no-ACL pool and ranks jobs using only listing data.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ESI_BASE = "https://esi.evetech.net"
COMPATIBILITY_DATE = os.getenv("ESI_COMPATIBILITY_DATE", "2025-12-16")
USER_AGENT = os.getenv(
    "EVE_USER_AGENT",
    "chatgpt-eve/freelance-jobs-radar (github.com/samson8964/chatgpt-eve)",
)


def get_json(session: requests.Session, path: str, params=None, retries: int = 3):
    url = f"{ESI_BASE}{path}"
    for attempt in range(retries):
        r = session.get(url, params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (420, 429) or 500 <= r.status_code < 600:
            time.sleep(min(2 ** attempt, 8))
            continue
        r.raise_for_status()
    raise RuntimeError(f"ESI request failed after {retries} attempts: {url}")


def fetch_public_jobs(session: requests.Session, limit: int = 100):
    jobs = []
    after = "0"
    seen = set()
    while True:
        payload = get_json(
            session,
            "/freelance-jobs",
            params={"after": after, "limit": limit},
        )
        batch = payload.get("freelance_jobs", [])
        if not batch:
            break
        for job in batch:
            jid = job.get("id")
            if jid and jid not in seen:
                seen.add(jid)
                jobs.append(job)
        cursor = payload.get("cursor") or {}
        nxt = cursor.get("after")
        if not nxt or nxt == after:
            break
        after = str(nxt)
    return jobs


def score(job):
    reward = job.get("reward") or {}
    progress = job.get("progress") or {}
    remaining_reward = float(reward.get("remaining") or 0)
    desired = float(progress.get("desired") or 0)
    current = float(progress.get("current") or 0)
    remaining_work = max(desired - current, 0)
    unit_reward = remaining_reward / remaining_work if remaining_work > 0 else 0
    return (unit_reward, remaining_reward)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--raw", default="artifacts/freelance_jobs_raw.json")
    ap.add_argument("--summary", default="artifacts/freelance_jobs_top.json")
    args = ap.parse_args()

    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "en",
            "X-Compatibility-Date": COMPATIBILITY_DATE,
        }
    )

    jobs = fetch_public_jobs(s)
    ranked = sorted(jobs, key=score, reverse=True)
    top = ranked[: max(args.top, 0)]

    Path(args.raw).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    Path(args.raw).write_text(
        json.dumps(
            {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "compatibility_date": COMPATIBILITY_DATE,
                "count": len(jobs),
                "jobs": jobs,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    rows = []
    for j in top:
        reward = j.get("reward") or {}
        progress = j.get("progress") or {}
        remaining_reward = float(reward.get("remaining") or 0)
        remaining_work = max(
            float(progress.get("desired") or 0) - float(progress.get("current") or 0),
            0,
        )
        detail = get_json(s, f"/freelance-jobs/{j.get('id')}") if j.get("id") else {}
        rows.append(
            {
                "id": j.get("id"),
                "name": j.get("name"),
                "state": j.get("state"),
                "reward_remaining": remaining_reward,
                "work_remaining": remaining_work,
                "reward_per_unit_remaining": (
                    remaining_reward / remaining_work if remaining_work > 0 else None
                ),
                "last_modified": j.get("last_modified"),
                "list_record": j,
                "detail": detail,
            }
        )

    Path(args.summary).write_text(
        json.dumps(
            {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "public_job_count": len(jobs),
                "top": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"public_job_count": len(jobs), "top": rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
