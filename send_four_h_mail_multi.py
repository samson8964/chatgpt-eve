from __future__ import annotations

import html
import os
import re
import time
from pathlib import Path

import pandas as pd
import requests

from send_eve_mail_dual import send_mail
from send_eve_mail_fast import fmt_isk, resolve_character

LATEST = Path("results/latest")
STATE = Path("results/state")
MAIL_TOP = int(os.getenv("MAIL_TOP", "10"))
POLICY_VERSION = "fourh-v2-incremental-1"
PREVIOUS_POLICY_VERSIONS = {"fourh-v2-exec-1", POLICY_VERSION}
RESEND_ABS_PROFIT = float(os.getenv("MAIL_RESEND_ABS_PROFIT", "20000000"))
RESEND_REL_PROFIT = float(os.getenv("MAIL_RESEND_REL_PROFIT", "0.10"))
RESEND_ROI_DELTA = float(os.getenv("MAIL_RESEND_ROI_DELTA", "0.02"))
REMIND_AFTER_HOURS = float(os.getenv("MAIL_REMIND_AFTER_HOURS", "6"))

CHANNELS = {
    "four-h-contract": {
        "path": LATEST / "four_h_contract_bargains.csv",
        "id_col": "contract_id",
        "profit_col": "best_net_profit",
        "roi_col": "best_roi",
        "title": "4-H合同捡漏V2",
    },
    "four-h-market": {
        "path": LATEST / "four_h_to_jita_buy.csv",
        "id_col": "type_id",
        "profit_col": "net_profit",
        "roi_col": "net_roi",
        "title": "4-H市场套利V2",
    },
}


def _read(path: Path) -> pd.DataFrame:
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


def _num(v, default=0.0):
    try:
        x = float(v)
        return default if pd.isna(x) else x
    except Exception:
        return default


def recipient_names():
    raw = os.getenv("EVE_MAIL_RECIPIENT_NAMES", "").strip()
    if raw:
        names = [x.strip() for x in raw.split(",") if x.strip()]
    else:
        names = [os.getenv("EVE_MAIL_RECIPIENT_NAME", "MikeChong").strip() or "MikeChong"]
    return list(dict.fromkeys(names))


def safe_key(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())
    return s.strip("_") or "recipient"


def state_path(channel: str, recipient_name: str) -> Path:
    return STATE / f"mail_last_{channel}_{safe_key(recipient_name)}.csv"


def build_candidates(channel: str):
    cfg = CHANNELS[channel]
    df = _read(cfg["path"])
    if df.empty or cfg["id_col"] not in df.columns:
        return []

    if "execution_status" in df.columns:
        df = df[df["execution_status"].fillna("").astype(str).str.upper().eq("SAFE")].copy()

    profit = pd.to_numeric(df.get(cfg["profit_col"]), errors="coerce").fillna(0.0)
    roi = pd.to_numeric(df.get(cfg["roi_col"]), errors="coerce").fillna(0.0)
    df = df.assign(_mail_profit=profit, _mail_roi=roi)
    df = df[(df["_mail_profit"] > 0) & (df["_mail_roi"] > 0)].copy()

    sort_cols = []
    ascending = []
    if "opportunity_score" in df.columns:
        sort_cols.append("opportunity_score")
        ascending.append(False)
    sort_cols += ["_mail_profit", "_mail_roi"]
    ascending += [False, False]
    df = df.sort_values(sort_cols, ascending=ascending).head(MAIL_TOP)

    out = []
    for _, r in df.iterrows():
        try:
            ident = int(float(r[cfg["id_col"]]))
        except Exception:
            continue
        out.append({
            "id": ident,
            "profit": float(r["_mail_profit"]),
            "roi": float(r["_mail_roi"]),
            "status": _text(r.get("execution_status"), "SAFE").upper(),
            "grade": _text(r.get("score_grade"), ""),
            "row": r,
        })
    return out


def _old_state_rows(channel: str, recipient_name: str):
    path = state_path(channel, recipient_name)
    if not path.exists():
        return None
    old = _read(path)
    if old.empty:
        return None
    required = {"policy_version", "rank", "id", "profit", "roi", "status", "grade", "sent_at"}
    if not required.issubset(old.columns):
        return "invalid"
    versions = {str(v) for v in old["policy_version"].fillna("")}
    if not versions.issubset(PREVIOUS_POLICY_VERSIONS):
        return "invalid"
    return old.sort_values("rank")


def notification_plan(channel: str, recipient_name: str, picked):
    """Return only actionable deltas.

    Membership churn no longer causes the complete TOP list to be resent. The plan
    contains newly-entered items, materially-changed existing items, and IDs that
    left the current pushed TOP. A six-hour reminder is retained as a compact
    periodic full reminder, not a half-hour membership-churn resend.
    """
    old = _old_state_rows(channel, recipient_name)
    if old is None:
        if not picked:
            return None
        return {
            "mode": "initial",
            "added": [dict(x, change_kind="新增") for x in picked],
            "changed": [],
            "removed": [],
            "current": picked,
        }
    if isinstance(old, str):
        if not picked:
            return None
        return {
            "mode": "refresh",
            "added": [dict(x, change_kind="当前") for x in picked],
            "changed": [],
            "removed": [],
            "current": picked,
        }

    old_by_id = {}
    for _, row in old.iterrows():
        try:
            old_by_id[int(float(row["id"]))] = row
        except Exception:
            continue
    cur_by_id = {int(x["id"]): x for x in picked}

    added = []
    changed = []
    removed = []

    for cur in picked:
        ident = int(cur["id"])
        prev = old_by_id.get(ident)
        if prev is None:
            added.append(dict(cur, change_kind="新增"))
            continue

        reasons = []
        old_profit = _num(prev.get("profit"))
        delta = abs(cur["profit"] - old_profit)
        rel = delta / max(abs(old_profit), 1.0)
        if delta >= RESEND_ABS_PROFIT or rel >= RESEND_REL_PROFIT:
            reasons.append(f"利润 {fmt_isk(old_profit)}→{fmt_isk(cur['profit'])}")
        old_roi = _num(prev.get("roi"))
        if abs(cur["roi"] - old_roi) >= RESEND_ROI_DELTA:
            reasons.append(f"ROI {old_roi:.1%}→{cur['roi']:.1%}")
        old_status = _text(prev.get("status"), "SAFE").upper()
        if cur["status"] != old_status:
            reasons.append(f"状态 {old_status}→{cur['status']}")
        old_grade = _text(prev.get("grade"), "")
        if cur["grade"] != old_grade:
            reasons.append(f"评级 {old_grade or '-'}→{cur['grade'] or '-'}")
        if reasons:
            item = dict(cur, change_kind="变化")
            item["change_reason"] = "；".join(reasons)
            changed.append(item)

    for ident, prev in old_by_id.items():
        if ident in cur_by_id:
            continue
        removed.append({
            "id": ident,
            "profit": _num(prev.get("profit")),
            "roi": _num(prev.get("roi")),
            "status": _text(prev.get("status"), "SAFE").upper(),
            "grade": _text(prev.get("grade"), ""),
        })

    if added or changed or removed:
        print(
            f"{channel} incremental trigger: "
            f"added={len(added)} changed={len(changed)} removed={len(removed)}"
        )
        return {
            "mode": "incremental",
            "added": added,
            "changed": changed,
            "removed": removed,
            "current": picked,
        }

    sent = pd.to_datetime(old["sent_at"], utc=True, errors="coerce").dropna()
    if sent.empty:
        return {
            "mode": "refresh",
            "added": [dict(x, change_kind="当前") for x in picked],
            "changed": [],
            "removed": [],
            "current": picked,
        } if picked else None

    age_h = (pd.Timestamp.now(tz="UTC") - sent.max()).total_seconds() / 3600.0
    if age_h >= REMIND_AFTER_HOURS and picked:
        print(f"{channel} reminder trigger: still SAFE after {age_h:.1f}h")
        return {
            "mode": "reminder",
            "added": [dict(x, change_kind="持续") for x in picked],
            "changed": [],
            "removed": [],
            "current": picked,
        }
    return None


def should_suppress(channel: str, recipient_name: str, picked) -> bool:
    return notification_plan(channel, recipient_name, picked) is None


def save_state(channel: str, recipient_name: str, picked):
    path = state_path(channel, recipient_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    sent_at = pd.Timestamp.now(tz="UTC").isoformat()
    rows = []
    for rank, c in enumerate(picked, 1):
        rows.append({
            "policy_version": POLICY_VERSION,
            "rank": rank,
            "id": c["id"],
            "profit": c["profit"],
            "roi": c["roi"],
            "status": c["status"],
            "grade": c["grade"],
            "sent_at": sent_at,
        })
    pd.DataFrame(
        rows,
        columns=["policy_version", "rank", "id", "profit", "roi", "status", "grade", "sent_at"],
    ).to_csv(path, index=False)


def _render_contract_item(c):
    r = c["row"]
    cid = c["id"]
    title = html.escape(_text(r.get("title"), "无标题"))
    route = html.escape(_text(r.get("best_route"), ""))
    items = html.escape(_text(r.get("top_items"), ""))
    stress = _num(r.get("stress_net_profit"))
    vol = _num(r.get("packaged_volume_m3"))
    score = _num(r.get("opportunity_score"))
    change = html.escape(_text(c.get("change_kind"), ""))
    reason = html.escape(_text(c.get("change_reason"), ""))
    prefix = f"<b>[{change}]</b> " if change else ""
    reason_line = f"变化：{reason}<br>" if reason else ""
    return (
        f"{prefix}<b>[{html.escape(c['grade'] or '-')}] {title}</b><br>"
        f"合同价 {fmt_isk(r.get('price',0))} · 净利 {fmt_isk(c['profit'])} · ROI {c['roi']:.1%}<br>"
        f"路线 {route} · 压力净利 {fmt_isk(stress)} · 评分 {score:.1f} · 体积 {vol:.0f}m3<br>"
        + reason_line
        + (f"主要物品：{items}<br>" if items else "")
        + f"<url=contract:0//{cid}><b>打开合同</b></url><br><br>"
    )


def _render_market_item(c):
    r = c["row"]
    tid = c["id"]
    name = html.escape(_text(r.get("item_name"), str(tid)))
    qty = int(_num(r.get("quantity"), 0))
    stress = _num(r.get("stress_net_profit"))
    fill_days = _num(r.get("estimated_fill_time_days"))
    liq = html.escape(_text(r.get("liquidity_label"), ""))
    score = _num(r.get("opportunity_score"))
    change = html.escape(_text(c.get("change_kind"), ""))
    reason = html.escape(_text(c.get("change_reason"), ""))
    prefix = f"<b>[{change}]</b> " if change else ""
    reason_line = f"变化：{reason}<br>" if reason else ""
    return (
        f"{prefix}<b>[{html.escape(c['grade'] or '-')}] {name} ×{qty:,}</b><br>"
        f"4-H买入 {fmt_isk(r.get('four_h_best_sell',0))}/件 · Jita买单 {fmt_isk(r.get('jita_best_buy',0))}/件<br>"
        f"净利 {fmt_isk(c['profit'])} · ROI {c['roi']:.1%} · 压力净利 {fmt_isk(stress)} · 评分 {score:.1f}<br>"
        f"流动性 {liq or '-'} · 预计消化 {fill_days:.2f}天 · 总体积 {_num(r.get('total_volume_m3')):.0f}m3<br>"
        + reason_line
        + f"<url=showinfo:{tid}><b>查看物品</b></url><br><br>"
    )


def _render_removed(channel: str, removed):
    if not removed:
        return ""
    parts = ["<b>退出当前推送TOP</b><br>"]
    noun = "合同" if channel == "four-h-contract" else "物品"
    for r in removed:
        parts.append(
            f"{noun}ID {r['id']} · 上次净利 {fmt_isk(r['profit'])} · ROI {r['roi']:.1%}"
            f" · 评级 {html.escape(r['grade'] or '-')}<br>"
        )
    parts.append("注：退出推送TOP不一定代表机会完全消失，也可能只是跌出当前TOP排名。<br><br>")
    return "".join(parts)


def render_notification(channel: str, stamp: str, plan):
    cfg = CHANNELS[channel]
    mode = plan["mode"]
    added = plan["added"]
    changed = plan["changed"]
    removed = plan["removed"]

    if mode == "incremental":
        subject = (
            f"{cfg['title']} 变动 {stamp} · "
            f"+{len(added)} ~{len(changed)} -{len(removed)}"
        )
        parts = [
            f"<b>{cfg['title']} · 增量变化提醒</b><br>{stamp}<br>",
            "本邮件只列本轮新增、重大变化和退出当前推送TOP的项目，不再重复发送整张旧榜单。<br><br>",
        ]
        current_delta = added + changed
    elif mode == "reminder":
        subject = f"{cfg['title']} 持续SAFE {stamp} · {len(added)}项"
        parts = [
            f"<b>{cfg['title']} · 6小时持续SAFE提醒</b><br>{stamp}<br><br>",
        ]
        current_delta = added
    else:
        subject = f"{cfg['title']} {stamp} · TOP{len(added)}"
        parts = [
            f"<b>{cfg['title']} · 当前SAFE机会</b><br>{stamp}<br><br>",
        ]
        current_delta = added

    renderer = _render_contract_item if channel == "four-h-contract" else _render_market_item
    for c in current_delta:
        parts.append(renderer(c))
    parts.append(_render_removed(channel, removed))
    return subject, "".join(parts)


def send_with_retry(recipient_id: int, subject: str, body: str, channel: str, name: str):
    for attempt in range(1, 4):
        try:
            print(f"sending {channel} to {name} ({recipient_id}) attempt={attempt}")
            return send_mail(recipient_id, subject, body, channel)
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            if status < 500 or attempt >= 3:
                raise
            time.sleep(2 * attempt)


def main():
    names = recipient_names()
    recipients = [(name, resolve_character(name)) for name in names]
    stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")
    failures = []

    for channel in ("four-h-contract", "four-h-market"):
        picked = build_candidates(channel)
        print(f"{channel}: SAFE candidates={len(picked)}")
        for name, recipient_id in recipients:
            plan = notification_plan(channel, name, picked)
            if plan is None:
                print(f"{channel} skipped for {name}: no material incremental change TOP{len(picked)}")
                continue
            subject, body = render_notification(channel, stamp, plan)
            try:
                send_with_retry(recipient_id, subject, body, channel, name)
                save_state(channel, name, picked)
            except Exception as exc:
                failures.append((channel, name, exc))
                print(f"::warning::{channel} mail failed for {name}: {type(exc).__name__}: {exc}")

    if failures:
        print(f"::warning::4-H mail delivery incomplete: failures={len(failures)}")
        for channel, name, exc in failures:
            print(f"mail failure detail: channel={channel} recipient={name} error={exc}")
        raise RuntimeError(f"4-H mail delivery failed for {len(failures)} channel/recipient attempt(s)")


if __name__ == "__main__":
    main()
