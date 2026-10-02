from __future__ import annotations

import html
import os
import re
import time
from pathlib import Path

import pandas as pd
import requests

from send_eve_mail_dual import send_mail
from send_eve_mail_fast import contract_is_live, fmt_isk, resolve_character

LATEST = Path("results/latest")
STATE = Path("results/state")
RESULT = LATEST / "high_value_contract_actionable.csv"

CHANNEL = "high-value-contract"
POLICY_VERSION = "high-value-contract-v1"
MAIL_TOP = int(os.getenv("HVC_MAIL_TOP", "10"))
MIN_PROFIT = float(os.getenv("HVC_MAIL_MIN_PROFIT", "500000000"))
MIN_ROI = float(os.getenv("HVC_MAIL_MIN_ROI", "0.10"))
RESEND_ABS_PROFIT = float(os.getenv("HVC_MAIL_RESEND_ABS_PROFIT", "100000000"))
RESEND_REL_PROFIT = float(os.getenv("HVC_MAIL_RESEND_REL_PROFIT", "0.10"))
RESEND_ROI_DELTA = float(os.getenv("HVC_MAIL_RESEND_ROI_DELTA", "0.02"))
REMIND_AFTER_HOURS = float(os.getenv("HVC_MAIL_REMIND_AFTER_HOURS", "6"))


def read_csv(path):
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def num(v, default=0.0):
    try:
        x = float(v)
        return default if pd.isna(x) else x
    except Exception:
        return default


def text(v, default=""):
    if v is None:
        return default
    s = str(v).strip()
    if not s or s.lower() in {"nan", "none"}:
        return default
    return s


def safe_key(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "recipient"


def state_path(recipient):
    return STATE / f"mail_last_{CHANNEL}_{safe_key(recipient)}.csv"


def recipient_names():
    raw = os.getenv("EVE_MAIL_RECIPIENT_NAMES", "").strip()
    if raw:
        names = [x.strip() for x in raw.split(",") if x.strip()]
    else:
        names = [os.getenv("EVE_MAIL_RECIPIENT_NAME", "MikeChong").strip() or "MikeChong"]
    return list(dict.fromkeys(names))


def build_candidates():
    df = read_csv(RESULT)
    if df.empty or "contract_id" not in df.columns:
        return []
    if "execution_status" in df.columns:
        df = df[df["execution_status"].fillna("").astype(str).str.upper().eq("SAFE")].copy()
    if "capital_bucket" in df.columns:
        df = df[df["capital_bucket"].fillna("").astype(str).eq("ACTIONABLE")].copy()
    if df.empty:
        return []

    df["_profit"] = pd.to_numeric(df.get("net_profit"), errors="coerce").fillna(0.0)
    df["_roi"] = pd.to_numeric(df.get("net_roi"), errors="coerce").fillna(0.0)
    df["_score"] = pd.to_numeric(df.get("opportunity_score"), errors="coerce").fillna(0.0)
    df["_stress"] = pd.to_numeric(df.get("stress_net_profit"), errors="coerce").fillna(0.0)
    df = df[
        (df["_profit"] >= MIN_PROFIT)
        & (df["_roi"] >= MIN_ROI)
        & (df["_stress"] > 0)
    ].copy()
    df.sort_values(["_score", "_stress", "_profit"], ascending=False, inplace=True)

    out = []
    for _, r in df.head(MAIL_TOP * 3).iterrows():
        try:
            cid = int(float(r["contract_id"]))
        except Exception:
            continue
        try:
            if not contract_is_live(cid):
                print(f"{CHANNEL}: stale contract skipped {cid}")
                continue
        except Exception as exc:
            print(f"{CHANNEL}: live check failed closed {cid}: {type(exc).__name__}: {exc}")
            continue
        out.append({
            "id": cid,
            "profit": float(r["_profit"]),
            "roi": float(r["_roi"]),
            "score": float(r["_score"]),
            "stress": float(r["_stress"]),
            "grade": text(r.get("score_grade")),
            "row": r,
        })
        if len(out) >= MAIL_TOP:
            break
    return out


def should_suppress(recipient, picked):
    path = state_path(recipient)
    if not path.exists():
        return not picked
    old = read_csv(path)
    if old.empty:
        return not picked
    required = {"policy_version", "id", "profit", "roi", "grade", "sent_at"}
    if not required.issubset(old.columns):
        return False
    if any(str(v) != POLICY_VERSION for v in old["policy_version"].fillna("")):
        return False

    current_ids = [int(x["id"]) for x in picked]
    old_ids = [int(x) for x in pd.to_numeric(old["id"], errors="coerce").dropna().astype(int).tolist()]
    if len(current_ids) != len(old_ids) or set(current_ids) != set(old_ids):
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
        old_profit = num(prev.get("profit"))
        delta = abs(cur["profit"] - old_profit)
        rel = delta / max(abs(old_profit), 1.0)
        if delta >= RESEND_ABS_PROFIT or rel >= RESEND_REL_PROFIT:
            return False
        if abs(cur["roi"] - num(prev.get("roi"))) >= RESEND_ROI_DELTA:
            return False
        if cur["grade"] != text(prev.get("grade")):
            return False

    sent = pd.to_datetime(old["sent_at"], utc=True, errors="coerce").dropna()
    if sent.empty:
        return False
    age_h = (pd.Timestamp.now(tz="UTC") - sent.max()).total_seconds() / 3600.0
    return age_h < REMIND_AFTER_HOURS


def save_state(recipient, picked):
    path = state_path(recipient)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = pd.Timestamp.now(tz="UTC").isoformat()
    rows = []
    for rank, c in enumerate(picked, 1):
        rows.append({
            "policy_version": POLICY_VERSION,
            "rank": rank,
            "id": c["id"],
            "profit": c["profit"],
            "roi": c["roi"],
            "grade": c["grade"],
            "sent_at": now,
        })
    pd.DataFrame(
        rows,
        columns=["policy_version", "rank", "id", "profit", "roi", "grade", "sent_at"],
    ).to_csv(path, index=False)


def loc_text(r):
    system = html.escape(text(r.get("system_name"), "未知"))
    station = html.escape(text(r.get("station_name"), ""))
    jumps = int(num(r.get("shortest_jumps_to_jita"), -1))
    risk = html.escape(text(r.get("risk_tier"), ""))
    bits = [system]
    if station:
        bits.append(station)
    if jumps >= 0:
        bits.append(f"Jita {jumps}跳")
    if risk:
        bits.append(risk)
    return " · ".join(bits)


def render(stamp, picked):
    subject = f"高价值合同捡漏 {stamp} · TOP{len(picked)}"
    parts = [
        f"<b>高价值合同捡漏 · 独立通道 · TOP{len(picked)}</b><br>{stamp}<br>",
        "只推送合同价>50亿且<=80亿、保守净利>=5亿、ROI>=10%、压力情景仍盈利的SAFE机会。<br>",
        "80亿-200亿仅观察；200亿以上仅研究，不会自动推送。现有其他捡漏通道规则未改变。<br><br>",
    ]
    for i, c in enumerate(picked, 1):
        r = c["row"]
        capital = "含资本舰" if bool(r.get("has_capital_ship", False)) else "无资本舰"
        parts.append(
            f"<b>{i}. [{html.escape(c['grade'] or '-')}] 合同 {c['id']}</b><br>"
            f"合同价 {fmt_isk(r.get('contract_price',0))} · 净利 {fmt_isk(c['profit'])} · ROI {c['roi']:.1%}<br>"
            f"证明 {html.escape(text(r.get('proof_basis')))} · 压力净利 {fmt_isk(c['stress'])} · {capital}<br>"
            f"现金底价 {fmt_isk(r.get('cash_floor_value',0))} · 7日保守价值 {fmt_isk(r.get('conservative_7d_value',0))} · "
            f"拆包保守最优 {fmt_isk(r.get('split_best_value',0))}<br>"
            f"普通物品：{html.escape(text(r.get('normal_items'), '无'))}<br>"
            f"资本舰：{html.escape(text(r.get('capital_items'), '无'))}<br>"
            f"{loc_text(r)}<br>"
            f"<url=contract:0//{c['id']}><b>打开合同</b></url><br><br>"
        )
    return subject, "".join(parts)


def send_with_retry(recipient_id, subject, body, name):
    for attempt in range(1, 4):
        try:
            print(f"sending {CHANNEL} to {name} ({recipient_id}) attempt={attempt}")
            return send_mail(recipient_id, subject, body, CHANNEL)
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            if status < 500 or attempt >= 3:
                raise
            time.sleep(2 * attempt)


def main():
    picked = build_candidates()
    print(f"{CHANNEL}: SAFE actionable candidates={len(picked)}")
    if not picked:
        print(f"{CHANNEL}: no qualifying opportunity; no mail sent")
        return

    stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")
    subject, body = render(stamp, picked)
    failures = []

    for name in recipient_names():
        rid = resolve_character(name)
        if should_suppress(name, picked):
            print(f"{CHANNEL} skipped for {name}: no material change TOP{len(picked)}")
            continue
        try:
            send_with_retry(rid, subject, body, name)
            save_state(name, picked)
        except Exception as exc:
            failures.append((name, exc))
            print(f"::warning::{CHANNEL} mail failed for {name}: {type(exc).__name__}: {exc}")

    if failures:
        raise RuntimeError(f"{CHANNEL} mail delivery failed for {len(failures)} recipient(s)")


if __name__ == "__main__":
    main()
