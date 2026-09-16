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
POLICY_VERSION = "fourh-v2-exec-1"
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


def should_suppress(channel: str, recipient_name: str, picked) -> bool:
    path = state_path(channel, recipient_name)
    if not path.exists():
        # Do not send an initial empty digest.
        return not picked

    old = _read(path)
    if old.empty:
        return not picked
    required = {"policy_version", "rank", "id", "profit", "roi", "status", "grade", "sent_at"}
    if not required.issubset(old.columns):
        return False
    if any(str(v) != POLICY_VERSION for v in old["policy_version"].fillna("")):
        return False

    old = old.sort_values("rank")
    current_ids = [int(x["id"]) for x in picked]
    old_ids = [int(x) for x in pd.to_numeric(old["id"], errors="coerce").dropna().astype(int).tolist()]
    if current_ids != old_ids:
        print(f"{channel} reminder trigger: TOP membership/rank changed")
        return False
    if not picked:
        return True

    old_by_id = {}
    for _, r in old.iterrows():
        try:
            old_by_id[int(float(r["id"]))] = r
        except Exception:
            continue

    for cur in picked:
        prev = old_by_id.get(cur["id"])
        if prev is None:
            return False
        old_profit = _num(prev.get("profit"))
        delta = abs(cur["profit"] - old_profit)
        rel = delta / max(abs(old_profit), 1.0)
        if delta >= RESEND_ABS_PROFIT or rel >= RESEND_REL_PROFIT:
            print(f"{channel} reminder trigger: {cur['id']} profit changed delta={delta:.0f} rel={rel:.1%}")
            return False
        old_roi = _num(prev.get("roi"))
        if abs(cur["roi"] - old_roi) >= RESEND_ROI_DELTA:
            print(f"{channel} reminder trigger: {cur['id']} ROI changed")
            return False
        if cur["status"] != _text(prev.get("status"), "SAFE").upper():
            return False
        if cur["grade"] != _text(prev.get("grade"), ""):
            return False

    sent = pd.to_datetime(old["sent_at"], utc=True, errors="coerce").dropna()
    if sent.empty:
        return False
    age_h = (pd.Timestamp.now(tz="UTC") - sent.max()).total_seconds() / 3600.0
    if age_h >= REMIND_AFTER_HOURS:
        print(f"{channel} reminder trigger: still SAFE after {age_h:.1f}h")
        return False
    return True


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
    pd.DataFrame(rows, columns=["policy_version", "rank", "id", "profit", "roi", "status", "grade", "sent_at"]).to_csv(path, index=False)


def render_contract(stamp: str, picked):
    subject = f"4-H合同捡漏V2 {stamp} · TOP{len(picked)}"
    if not picked:
        return subject, f"<b>4-H合同捡漏 · Opportunity Engine V2</b><br>{stamp}<br><br>当前没有 SAFE 机会。"
    parts = [
        f"<b>4-H合同捡漏 · Opportunity Engine V2 · TOP{len(picked)}</b><br>{stamp}<br>",
        "仅推送实时复核为 SAFE 的合同；支持 4-H 本地买单或 Jita 实时买单兑现。<br><br>",
    ]
    for i, c in enumerate(picked, 1):
        r = c["row"]
        cid = c["id"]
        title = html.escape(_text(r.get("title"), "无标题"))
        route = html.escape(_text(r.get("best_route"), ""))
        items = html.escape(_text(r.get("top_items"), ""))
        stress = _num(r.get("stress_net_profit"))
        vol = _num(r.get("packaged_volume_m3"))
        score = _num(r.get("opportunity_score"))
        parts.append(
            f"<b>{i}. [{html.escape(c['grade'] or '-')}] {title}</b><br>"
            f"合同价 {fmt_isk(r.get('price',0))} · 净利 {fmt_isk(c['profit'])} · ROI {c['roi']:.1%}<br>"
            f"路线 {route} · 压力净利 {fmt_isk(stress)} · 评分 {score:.1f} · 体积 {vol:.0f}m3<br>"
            + (f"主要物品：{items}<br>" if items else "")
            + f"<url=contract:0//{cid}><b>打开合同</b></url><br><br>"
        )
    return subject, "".join(parts)


def render_market(stamp: str, picked):
    subject = f"4-H市场套利V2 {stamp} · TOP{len(picked)}"
    if not picked:
        return subject, f"<b>4-H市场 → Jita 套利 · Opportunity Engine V2</b><br>{stamp}<br><br>当前没有 SAFE 机会。"
    parts = [
        f"<b>4-H市场 → Jita 4-4 · Opportunity Engine V2 · TOP{len(picked)}</b><br>{stamp}<br>",
        "4-H 真实卖单买入 → Jita 实时买单卖出；仅推送 SAFE，已计销售税。<br><br>",
    ]
    for i, c in enumerate(picked, 1):
        r = c["row"]
        tid = c["id"]
        name = html.escape(_text(r.get("item_name"), str(tid)))
        qty = int(_num(r.get("quantity"), 0))
        stress = _num(r.get("stress_net_profit"))
        fill_days = _num(r.get("estimated_fill_time_days"))
        liq = html.escape(_text(r.get("liquidity_label"), ""))
        score = _num(r.get("opportunity_score"))
        parts.append(
            f"<b>{i}. [{html.escape(c['grade'] or '-')}] {name} ×{qty:,}</b><br>"
            f"4-H买入 {fmt_isk(r.get('four_h_best_sell',0))}/件 · Jita买单 {fmt_isk(r.get('jita_best_buy',0))}/件<br>"
            f"净利 {fmt_isk(c['profit'])} · ROI {c['roi']:.1%} · 压力净利 {fmt_isk(stress)} · 评分 {score:.1f}<br>"
            f"流动性 {liq or '-'} · 预计消化 {fill_days:.2f}天 · 总体积 {_num(r.get('total_volume_m3')):.0f}m3<br>"
            f"<url=showinfo:{tid}><b>查看物品</b></url><br><br>"
        )
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
            if should_suppress(channel, name, picked):
                print(f"{channel} skipped for {name}: no material change TOP{len(picked)}")
                continue
            subject, body = render_contract(stamp, picked) if channel == "four-h-contract" else render_market(stamp, picked)
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


if __name__ == "__main__":
    main()
