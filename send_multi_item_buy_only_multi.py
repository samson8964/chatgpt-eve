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
POLICY_VERSION = "buyonly-v2-exec-2"
RESEND_ABS_PROFIT = float(os.getenv("MAIL_RESEND_ABS_PROFIT", "20000000"))
RESEND_REL_PROFIT = float(os.getenv("MAIL_RESEND_REL_PROFIT", "0.10"))
RESEND_ROI_DELTA = float(os.getenv("MAIL_RESEND_ROI_DELTA", "0.02"))
REMIND_AFTER_HOURS = float(os.getenv("MAIL_REMIND_AFTER_HOURS", "6"))


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
    return Path("results/state") / f"mail_last_multi_buyonly_top10_{safe_recipient_key(name)}.csv"


def read_csv(path: Path):
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _text(v, default=""):
    if v is None:
        return default
    s = str(v).strip()
    if not s or s.lower() in {"nan", "none"}:
        return default
    return s


def _snapshot(c):
    row = c.get("row")
    status = "SAFE"
    grade = ""
    if row is not None:
        status = _text(row.get("execution_status"), "SAFE").upper()
        grade = _text(row.get("score_grade"), _text(row.get("recommendation"), ""))
    return {
        "contract_id": int(c["contract_id"]),
        "metric": float(c.get("gap", 0.0) or 0.0),
        "roi": float(c.get("roi", 0.0) or 0.0),
        "status": status,
        "grade": grade,
    }


def load_signature(path: Path):
    df = read_csv(path)
    if df.empty or "contract_id" not in df.columns:
        return []
    if "rank" in df.columns:
        df = df.sort_values("rank")
    return [int(x) for x in pd.to_numeric(df["contract_id"], errors="coerce").dropna().astype(int).tolist()]


def should_suppress(path: Path, picked):
    current = [_snapshot(c) for c in picked]
    current_ids = [x["contract_id"] for x in current]

    if not path.exists():
        print(f"{CHANNEL} reminder trigger: no prior recipient state")
        return False

    state = read_csv(path)
    previous_ids = load_signature(path)
    if current_ids != previous_ids:
        print(f"{CHANNEL} reminder trigger: TOP membership/rank changed")
        return False

    # Avoid periodic empty digests. A transition from non-empty to empty is caught above.
    if not current:
        return True

    required = {"policy_version", "metric", "roi", "status", "grade", "sent_at"}
    if state.empty or not required.issubset(state.columns):
        print(f"{CHANNEL} reminder trigger: policy/state upgraded")
        return False
    if "rank" in state.columns:
        state = state.sort_values("rank")
    if any(str(v) != POLICY_VERSION for v in state["policy_version"].fillna("")):
        print(f"{CHANNEL} reminder trigger: policy version changed")
        return False

    old_by_id = {}
    for _, r in state.iterrows():
        try:
            old_by_id[int(float(r["contract_id"]))] = r
        except Exception:
            continue

    for cur in current:
        cid = cur["contract_id"]
        old = old_by_id.get(cid)
        if old is None:
            print(f"{CHANNEL} reminder trigger: new contract {cid}")
            return False

        old_metric = float(pd.to_numeric(old.get("metric"), errors="coerce") or 0.0)
        delta = abs(cur["metric"] - old_metric)
        rel = delta / max(abs(old_metric), 1.0)
        if delta >= RESEND_ABS_PROFIT or rel >= RESEND_REL_PROFIT:
            print(
                f"{CHANNEL} reminder trigger: contract {cid} value changed "
                f"delta={delta:.0f} rel={rel:.1%}"
            )
            return False

        old_roi = float(pd.to_numeric(old.get("roi"), errors="coerce") or 0.0)
        if abs(cur["roi"] - old_roi) >= RESEND_ROI_DELTA:
            print(
                f"{CHANNEL} reminder trigger: contract {cid} ROI changed "
                f"delta={abs(cur['roi']-old_roi):.2%}"
            )
            return False

        if cur["status"] != _text(old.get("status"), "SAFE").upper():
            print(f"{CHANNEL} reminder trigger: contract {cid} execution status changed")
            return False
        if cur["grade"] != _text(old.get("grade"), ""):
            print(f"{CHANNEL} reminder trigger: contract {cid} grade changed")
            return False

    try:
        sent = pd.to_datetime(state["sent_at"], utc=True, errors="coerce").dropna()
        if sent.empty:
            print(f"{CHANNEL} reminder trigger: missing last-sent timestamp")
            return False
        age_h = (pd.Timestamp.now(tz="UTC") - sent.max()).total_seconds() / 3600.0
        if age_h >= REMIND_AFTER_HOURS:
            print(f"{CHANNEL} reminder trigger: still SAFE after {age_h:.1f}h")
            return False
    except Exception:
        print(f"{CHANNEL} reminder trigger: unreadable last-sent timestamp")
        return False

    return True


def save_signature(path: Path, picked):
    path.parent.mkdir(parents=True, exist_ok=True)
    sent_at = pd.Timestamp.now(tz="UTC").isoformat()
    rows = []
    for i, c in enumerate(picked, 1):
        snap = _snapshot(c)
        rows.append(
            {
                "rank": i,
                "contract_id": snap["contract_id"],
                "policy_version": POLICY_VERSION,
                "metric": snap["metric"],
                "roi": snap["roi"],
                "status": snap["status"],
                "grade": snap["grade"],
                "sent_at": sent_at,
            }
        )
    pd.DataFrame(
        rows,
        columns=[
            "rank",
            "contract_id",
            "policy_version",
            "metric",
            "roi",
            "status",
            "grade",
            "sent_at",
        ],
    ).to_csv(path, index=False)


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


def _safe_v2_candidates(candidates):
    """V2 never auto-mails CHANGED/DANGER opportunities.

    Legacy rows without execution_status remain eligible so rollback/old result files
    continue to work without changing this sender again.
    """
    out = []
    removed = 0
    for c in candidates:
        row = c.get("row")
        status = "SAFE"
        if row is not None and "execution_status" in row.index:
            status = str(row.get("execution_status", "SAFE") or "SAFE").upper()
        if status != "SAFE":
            removed += 1
            continue
        out.append(c)
    if removed:
        print(f"{CHANNEL}: V2 status gate removed={removed} non-SAFE candidates")
    return out


def render(stamp, candidates, picked, removed, history):
    if not picked:
        return (
            f"多件合同捡漏·Jita买单 {stamp} · 暂无强机会",
            f"<b>多件物品合同捡漏 · Buy-Only V2</b><br>{stamp}<br><br>"
            f"当前无满足条件且仍有效的 SAFE 合同；候选 {len(candidates)}，发送前失效/不可见 {removed}。<br>"
            "V2仅自动推送实时复核为SAFE的机会；Jita按真实买单深度估值。",
        )

    parts = [
        f"<b>多件物品合同捡漏 · Opportunity Engine V2 · TOP{len(picked)}</b><br>{stamp}<br>",
        f"SAFE强候选 {len(candidates)} · 发送前失效/不可见 {removed}<br>",
        "最终估值使用实时Jita 4-4买单深度；CHANGED/DANGER不会自动推送。<br>",
        "同一合同净价值变化≥20M或≥10%、ROI变化≥2个百分点、等级变化，或持续SAFE满6小时会再次提醒。<br>"
        "合同价>50亿、SKIN/SKINR价值占比≥50%、不可达或未确认可访问的陌生玩家建筑已剔除。<br><br>",
    ]
    for i, c in enumerate(picked, 1):
        count = push_count(history, c["contract_id"]) + 1
        parts.append(f"<b>本合同累计推送：第 {count} 次</b><br>")
        parts.append(templates.multi_item_html(i, c))
    return f"多件合同捡漏V2 {stamp} · TOP{len(picked)}", "".join(parts)


def main():
    if not base_multi.base.API_KEY:
        raise RuntimeError("Missing EVE_MAIL_API_KEY")

    names = recipient_names()
    primary = os.getenv("EVE_MAIL_RECIPIENT_NAME", "").strip() or names[0]
    recipients = [(name, resolve_character(name)) for name in names]
    candidates = _safe_v2_candidates(base_multi.build_candidates())
    picked, removed = base_multi.live_pick(candidates)
    history = load_history()
    stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")
    cycle_recorded = False
    failures = []

    for name, recipient_id in recipients:
        path = state_path(name)
        if should_suppress(path, picked):
            print(f"{CHANNEL} skipped for {name}: no material change TOP{len(picked)}")
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

    if failures:
        primary_failures = [exc for name, exc in failures if name.casefold() == primary.casefold()]
        print(
            f"::warning::{CHANNEL} delivery incomplete: failures={len(failures)} "
            f"primary_failures={len(primary_failures)}; scan results remain valid and will be saved."
        )
        for name, exc in failures:
            print(f"mail failure detail: recipient={name} error={exc}")


if __name__ == "__main__":
    main()
