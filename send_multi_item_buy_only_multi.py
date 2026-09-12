from __future__ import annotations

import os
import re
import time
from pathlib import Path

import pandas as pd
import requests

import buy_only_mail_templates as templates
import send_multi_item_mail as base_multi
from send_eve_mail_fast import resolve_character

HISTORY = Path("results/state/mail_push_history.csv")
CHANNEL = "multi-item-buy-only"


def recipient_names():
    raw = os.getenv("EVE_MAIL_RECIPIENT_NAMES", "").strip()
    if raw:
        names = [x.strip() for x in raw.split(",") if x.strip()]
    else:
        names = [base_multi.base.RECIPIENT_NAME]
    return list(dict.fromkeys(names))


def safe_recipient_key(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())
    return s.strip("_") or "recipient"


def state_path(name: str) -> Path:
    # New state namespace intentionally forces one fresh mail after the strategy migration.
    return Path("results/state") / f"mail_last_multi_buyonly_top10_{safe_recipient_key(name)}.csv"


def read_csv(path: Path):
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def load_signature(path: Path):
    df = read_csv(path)
    if df.empty or "contract_id" not in df.columns:
        return []
    if "rank" in df.columns:
        df = df.sort_values("rank")
    return [int(x) for x in pd.to_numeric(df["contract_id"], errors="coerce").dropna().astype(int).tolist()]


def save_signature(path: Path, picked):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"rank": i, "contract_id": int(c["contract_id"])} for i, c in enumerate(picked, 1)]
    pd.DataFrame(rows, columns=["rank", "contract_id"]).to_csv(path, index=False)


def load_history():
    df = read_csv(HISTORY)
    cols = ["channel", "contract_id", "last_sent_at", "metric", "push_count"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    for c in cols:
        if c not in df.columns:
            df[c] = 0 if c in {"contract_id", "metric", "push_count"} else ""
    df["contract_id"] = pd.to_numeric(df["contract_id"], errors="coerce").fillna(0).astype(int)
    df["push_count"] = pd.to_numeric(df["push_count"], errors="coerce").fillna(0).astype(int)
    return df[cols].copy()


def push_count(history, cid):
    if history.empty:
        return 0
    mask = (history["channel"].astype(str) == CHANNEL) & (history["contract_id"].astype(int) == int(cid))
    if not mask.any():
        return 0
    return int(history.loc[mask, "push_count"].max())


def record_cycle(history, picked):
    history = history.copy()
    now = pd.Timestamp.now(tz="UTC").isoformat()
    for c in picked:
        cid = int(c["contract_id"])
        metric = float(c.get("gap", 0) or 0)
        mask = (history["channel"].astype(str) == CHANNEL) & (history["contract_id"].astype(int) == cid)
        if mask.any():
            idx = history.index[mask][0]
            history.at[idx, "last_sent_at"] = now
            history.at[idx, "metric"] = metric
            history.at[idx, "push_count"] = int(history.at[idx, "push_count"] or 0) + 1
        else:
            history.loc[len(history)] = {
                "channel": CHANNEL,
                "contract_id": cid,
                "last_sent_at": now,
                "metric": metric,
                "push_count": 1,
            }
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    history.to_csv(HISTORY, index=False)
    return history


def send_with_retry(recipient_id, subject, body, name):
    for attempt in range(1, 4):
        try:
            print(f"sending {CHANNEL} to {name} ({recipient_id}) attempt={attempt}")
            return base_multi.base.send_mail(recipient_id, subject, body, CHANNEL)
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            if status < 500 or attempt >= 3:
                raise
            delay = 2 * attempt
            print(f"mail upstream HTTP {status}; retry {name} in {delay}s")
            time.sleep(delay)


def render(stamp, candidates, picked, removed, history):
    if not picked:
        return (
            f"多件合同捡漏·Jita买单 {stamp} · 暂无强机会",
            f"<b>多件物品合同捡漏 · Buy-Only</b><br>{stamp}<br><br>"
            f"当前无满足条件且仍有效的合同；候选 {len(candidates)}，发送前失效/不可见 {removed}。<br>"
            "仅按Jita 4-4真实买单深度估值；合同价≤50亿、净利润≥30M、ROI≥10%，不参考卖价。",
        )

    parts = [
        f"<b>多件物品合同捡漏 · Jita买单 TOP{len(picked)}</b><br>{stamp}<br>",
        f"强候选 {len(candidates)} · 发送前失效/不可见 {removed}<br>",
        "仅按Jita 4-4真实买单深度估值；买单吃不掉的剩余数量按0。不参考卖价。<br>",
        "合同价>50亿、SKIN/SKINR价值占比≥50%、不可达或未确认可访问的陌生玩家建筑已剔除。<br><br>",
    ]
    for i, c in enumerate(picked, 1):
        count = push_count(history, c["contract_id"]) + 1
        parts.append(f"<b>本合同累计推送：第 {count} 次</b><br>")
        parts.append(templates.multi_item_html(i, c))
    return f"多件合同捡漏·Jita买单 {stamp} · TOP{len(picked)}", "".join(parts)


def main():
    if not base_multi.base.API_KEY:
        raise RuntimeError("Missing EVE_MAIL_API_KEY")

    names = recipient_names()
    primary = os.getenv("EVE_MAIL_RECIPIENT_NAME", "").strip() or names[0]
    recipients = [(name, resolve_character(name)) for name in names]
    candidates = base_multi.build_candidates()
    picked, removed = base_multi.live_pick(candidates)
    signature = [int(c["contract_id"]) for c in picked]
    history = load_history()
    stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")
    cycle_recorded = False
    failures = []

    for name, recipient_id in recipients:
        path = state_path(name)
        if signature == load_signature(path):
            print(f"{CHANNEL} skipped for {name}: unchanged TOP{len(signature)}")
            continue
        subject, body = render(stamp, candidates, picked, removed, history)
        try:
            send_with_retry(recipient_id, subject, body, name)
            save_signature(path, picked)
            if picked and not cycle_recorded:
                history = record_cycle(history, picked)
                cycle_recorded = True
        except Exception as exc:
            failures.append((name, exc))
            print(f"::warning::{CHANNEL} failed for {name}: {type(exc).__name__}: {exc}")

    primary_failure = next((exc for name, exc in failures if name.casefold() == primary.casefold()), None)
    if primary_failure is not None:
        raise RuntimeError(f"Primary multi-item recipient {primary} mail failed") from primary_failure
    if failures:
        print("secondary multi-item recipient failures did not invalidate completed scan/results")


if __name__ == "__main__":
    main()
