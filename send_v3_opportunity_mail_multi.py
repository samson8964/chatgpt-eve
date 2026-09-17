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
MAIL_TOP = int(os.getenv("MAIL_TOP", "10"))
POLICY_VERSION = "opportunity-v3-supplemental-1"
REMIND_AFTER_HOURS = float(os.getenv("MAIL_REMIND_AFTER_HOURS", "6"))
RESEND_ABS_PROFIT = float(os.getenv("MAIL_RESEND_ABS_PROFIT", "20000000"))
RESEND_REL_PROFIT = float(os.getenv("MAIL_RESEND_REL_PROFIT", "0.10"))
RESEND_ROI_DELTA = float(os.getenv("MAIL_RESEND_ROI_DELTA", "0.02"))


def _read(path):
    if not Path(path).exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _num(v, default=0.0):
    try:
        x = float(v)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _text(v, default=""):
    s = str(v if v is not None else "").strip()
    return default if not s or s.lower() in {"nan", "none"} else s


def recipient_names():
    raw = os.getenv("EVE_MAIL_RECIPIENT_NAMES", "MikeChong,Vektor Yang")
    return list(dict.fromkeys(x.strip() for x in raw.split(",") if x.strip()))


def _safe_key(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "recipient"


def _state_path(channel, name):
    return STATE / f"mail_last_{channel}_{_safe_key(name)}.csv"


def _build_contract_candidates():
    df = _read(LATEST / "contract_opportunities_v3.csv")
    if df.empty or "contract_id" not in df.columns:
        return []
    if "execution_status" in df.columns:
        df = df[df["execution_status"].fillna("").astype(str).str.upper().eq("SAFE")].copy()
    df["_profit"] = pd.to_numeric(df.get("net_profit"), errors="coerce").fillna(0.0)
    df["_roi"] = pd.to_numeric(df.get("net_roi"), errors="coerce").fillna(0.0)
    class_rank = {"CASH_FLOOR": 0, "EXCHANGE_FULL": 1, "EXCHANGE_CASH_FLOOR": 2, "LIQUIDITY_SELL": 3}
    df["_class_rank"] = df.get("opportunity_class", "").map(class_rank).fillna(9)
    df = df[(df["_profit"] > 0) & (df["_roi"] > 0)].sort_values(["_class_rank", "_profit", "_roi"], ascending=[True, False, False])
    out = []
    for _, r in df.iterrows():
        cid = int(float(r["contract_id"]))
        cls = _text(r.get("opportunity_class"), "V3")
        out.append({"id": f"{cls}:{cid}", "contract_id": cid, "profit": float(r["_profit"]), "roi": float(r["_roi"]), "status": "SAFE", "grade": cls, "row": r})
        if len(out) >= MAIL_TOP:
            break
    return out


def _build_reverse_candidates():
    df = _read(LATEST / "four_h_reverse_v3.csv")
    if df.empty or "type_id" not in df.columns:
        return []
    df = df[df.get("execution_status", "").fillna("").astype(str).str.upper().eq("SAFE")].copy()
    df["_profit"] = pd.to_numeric(df.get("net_profit"), errors="coerce").fillna(0.0)
    df["_roi"] = pd.to_numeric(df.get("net_roi"), errors="coerce").fillna(0.0)
    df = df[(df["_profit"] > 0) & (df["_roi"] > 0)].sort_values(["_profit", "_roi"], ascending=False)
    out = []
    for _, r in df.head(MAIL_TOP).iterrows():
        tid = int(float(r["type_id"]))
        out.append({"id": f"JITA_TO_4H:{tid}", "profit": float(r["_profit"]), "roi": float(r["_roi"]), "status": "SAFE", "grade": _text(r.get("score_grade"), ""), "row": r})
    return out


def _build_bpc_resale_candidates():
    df = _read(LATEST / "bpc_value_opportunities_v2.csv")
    if df.empty or "contract_id" not in df.columns:
        return []
    status = df.get("v2_value_status", "").fillna("").astype(str).eq("VALUE_SIGNAL")
    live = df.get("v2_contract_live", False).fillna(False).astype(str).str.lower().isin(["true", "1", "yes"])
    samples = pd.to_numeric(df.get("bpc_market_sample_count"), errors="coerce").fillna(0)
    discount = -pd.to_numeric(df.get("bpc_discount_vs_median"), errors="coerce").fillna(0)
    surplus = pd.to_numeric(df.get("bpc_intrinsic_value_surplus"), errors="coerce").fillna(0)
    confidence = pd.to_numeric(df.get("v2_value_confidence"), errors="coerce").fillna(0)
    risk = pd.to_numeric(df.get("risk_rank"), errors="coerce").fillna(9)
    player = df.get("is_player_structure", False).fillna(False).astype(str).str.lower().isin(["true", "1", "yes"])
    friendly = df.get("friendly_sov", False).fillna(False).astype(str).str.lower().isin(["true", "1", "yes"]) | df.get("friendly_region", False).fillna(False).astype(str).str.lower().isin(["true", "1", "yes"])
    keep = status & live & (samples >= 10) & (discount >= 0.30) & (surplus >= 50_000_000) & (confidence >= 0.70) & (risk <= 2) & (~player | friendly)
    df = df[keep].copy()
    if df.empty:
        return []
    df["_surplus"] = surplus[keep]
    df["_discount"] = discount[keep]
    df = df.sort_values(["v2_value_score", "_surplus", "_discount"], ascending=False)
    out = []
    for _, r in df.head(MAIL_TOP).iterrows():
        cid = int(float(r["contract_id"]))
        out.append({"id": f"BPC_RESALE:{cid}", "contract_id": cid, "profit": _num(r.get("bpc_intrinsic_value_surplus")), "roi": _num(-r.get("bpc_discount_vs_median", 0)), "status": "WATCH", "grade": "BPC_RESALE", "row": r})
    return out


def _live_filter(channel, candidates):
    if channel not in {"v3-contract", "v3-bpc-resale"}:
        return candidates
    out = []
    for c in candidates:
        try:
            if contract_is_live(int(c["contract_id"])):
                out.append(c)
        except Exception:
            continue
    return out


def _suppress(channel, name, picked):
    path = _state_path(channel, name)
    if not path.exists():
        return not picked
    old = _read(path)
    if old.empty:
        return not picked
    required = {"policy_version", "id", "profit", "roi", "status", "grade", "sent_at"}
    if not required.issubset(old.columns) or any(str(v) != POLICY_VERSION for v in old["policy_version"].fillna("")):
        return False
    cur_ids = {str(c["id"]) for c in picked}
    old_ids = set(old["id"].fillna("").astype(str))
    if cur_ids != old_ids:
        print(f"{channel} reminder trigger: membership changed")
        return False
    if not picked:
        return True
    old_by_id = {str(r["id"]): r for _, r in old.iterrows()}
    for cur in picked:
        prev = old_by_id.get(str(cur["id"]))
        if prev is None:
            return False
        old_profit = _num(prev.get("profit"))
        delta = abs(cur["profit"] - old_profit)
        rel = delta / max(abs(old_profit), 1.0)
        if delta >= RESEND_ABS_PROFIT or rel >= RESEND_REL_PROFIT:
            return False
        if abs(cur["roi"] - _num(prev.get("roi"))) >= RESEND_ROI_DELTA:
            return False
        if cur["status"] != _text(prev.get("status")) or cur["grade"] != _text(prev.get("grade")):
            return False
    sent = pd.to_datetime(old["sent_at"], utc=True, errors="coerce").dropna()
    if sent.empty:
        return False
    age = (pd.Timestamp.now(tz="UTC") - sent.max()).total_seconds() / 3600.0
    return age < REMIND_AFTER_HOURS


def _save(channel, name, picked):
    path = _state_path(channel, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = pd.Timestamp.now(tz="UTC").isoformat()
    rows = [{"policy_version": POLICY_VERSION, "rank": i, "id": c["id"], "profit": c["profit"], "roi": c["roi"], "status": c["status"], "grade": c["grade"], "sent_at": now} for i, c in enumerate(picked, 1)]
    pd.DataFrame(rows, columns=["policy_version", "rank", "id", "profit", "roi", "status", "grade", "sent_at"]).to_csv(path, index=False)


def _contract_digest(stamp, picked):
    labels = {"CASH_FLOOR": "现金底价", "EXCHANGE_FULL": "以物换物", "EXCHANGE_CASH_FLOOR": "以物换物·现金底价", "LIQUIDITY_SELL": "保守挂卖"}
    subject = f"V3补充捡漏 {stamp} · TOP{len(picked)}"
    parts = [f"<b>Opportunity Engine V3 · 补充机会 TOP{len(picked)}</b><br>{stamp}<br>", "不会改变现有V2 SAFE频道；这里只补充V2容易漏掉的机会。<br><br>"]
    for i, c in enumerate(picked, 1):
        r = c["row"]
        cls = _text(r.get("opportunity_class"))
        parts.append(f"<b>{i}. {labels.get(cls, cls)} · 合同 {c['contract_id']}</b><br>")
        parts.append(f"净利 {fmt_isk(c['profit'])} · ROI {c['roi']:.1%} · 压力净利 {fmt_isk(r.get('stress_net_profit',0))}<br>")
        if cls in {"CASH_FLOOR", "EXCHANGE_CASH_FLOOR"}:
            parts.append(f"现金底价覆盖 {_num(r.get('cash_floor_coverage')):.0%}；未覆盖物品按0 ISK。<br>")
        if cls.startswith("EXCHANGE"):
            parts.append(f"需提供物品实时采购成本 {fmt_isk(r.get('requested_goods_cost',0))} · {html.escape(_text(r.get('requested_items')))}<br>")
        if cls == "LIQUIDITY_SELL":
            parts.append(f"预计最慢消化 {_num(r.get('extra_metric')):.2f}天；使用实时最低卖价/7日/30日成交锚中的保守值。<br>")
        parts.append(f"收到：{html.escape(_text(r.get('included_items')))}<br>物流预留 {fmt_isk(r.get('haul_reserve',0))} · {html.escape(_text(r.get('system_name')))} · {html.escape(_text(r.get('risk_tier')))}<br>")
        parts.append(f"<url=contract:0//{c['contract_id']}><b>打开合同</b></url><br><br>")
    return subject, "".join(parts)


def _reverse_digest(stamp, picked):
    subject = f"Jita→4-H套利V3 {stamp} · TOP{len(picked)}"
    parts = [f"<b>Jita → 4-H 反向套利 · V3 · TOP{len(picked)}</b><br>{stamp}<br>", "Jita实时卖单采购 → 4-H真实买单兑现；已扣销售税和V3物流预留。<br><br>"]
    for i, c in enumerate(picked, 1):
        r = c["row"]
        parts.append(f"<b>{i}. {html.escape(_text(r.get('item_name')))} ×{int(_num(r.get('quantity'))):,}</b><br>Jita买入 {fmt_isk(r.get('jita_best_sell',0))}/件 · 4-H买单 {fmt_isk(r.get('four_h_best_buy',0))}/件<br>净利 {fmt_isk(c['profit'])} · ROI {c['roi']:.1%} · 压力净利 {fmt_isk(r.get('stress_net_profit',0))}<br>物流预留 {fmt_isk(r.get('haul_cost',0))} · 路线 {int(_num(r.get('route_jumps')))}跳 · 总体积 {_num(r.get('total_volume_m3')):.0f}m3<br><url=showinfo:{int(float(r['type_id']))}><b>查看物品</b></url><br><br>")
    return subject, "".join(parts)


def _bpc_digest(stamp, picked):
    subject = f"BPC转售观察V3 {stamp} · TOP{len(picked)}"
    parts = [f"<b>BPC转售观察 · V3 · TOP{len(picked)}</b><br>{stamp}<br>", "这是强低估信号，不是即时可兑现利润；仅纳入≥10个可比样本、相对中位价便宜≥30%、理论价值差≥50M且高置信度的合同。<br><br>"]
    for i, c in enumerate(picked, 1):
        r = c["row"]
        discount = -_num(r.get("bpc_discount_vs_median"))
        parts.append(f"<b>{i}. {html.escape(_text(r.get('blueprint_name'), _text(r.get('blueprints'))))}</b><br>合同价 {fmt_isk(r.get('contract_price',0))} · 理论价值差 {fmt_isk(r.get('bpc_intrinsic_value_surplus',0))}<br>同类中位 {fmt_isk(r.get('bpc_market_median_per_run',0))}/流程 · 当前 {fmt_isk(r.get('bpc_current_cost_per_run',0))}/流程 · 低估 {discount:.1%}<br>样本 {int(_num(r.get('bpc_market_sample_count')))} · 置信度 {_num(r.get('v2_value_confidence')):.0%} · {html.escape(_text(r.get('system_name')))}<br><url=contract:0//{c['contract_id']}><b>打开合同</b></url><br><br>")
    return subject, "".join(parts)


def _send_retry(recipient_id, subject, body, channel, name):
    for attempt in range(1, 4):
        try:
            return send_mail(recipient_id, subject, body, channel)
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            if status < 500 or attempt >= 3:
                raise
            time.sleep(attempt * 2)


def main():
    channels = [
        ("v3-contract", _build_contract_candidates, _contract_digest),
        ("v3-reverse", _build_reverse_candidates, _reverse_digest),
        ("v3-bpc-resale", _build_bpc_resale_candidates, _bpc_digest),
    ]
    recipients = [(name, resolve_character(name)) for name in recipient_names()]
    stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")
    failures = []
    for channel, builder, renderer in channels:
        picked = _live_filter(channel, builder())
        print(f"{channel}: candidates={len(picked)}")
        for name, rid in recipients:
            if _suppress(channel, name, picked):
                print(f"{channel} skipped for {name}: no material change")
                continue
            subject, body = renderer(stamp, picked)
            try:
                _send_retry(rid, subject, body, channel, name)
                _save(channel, name, picked)
            except Exception as exc:
                failures.append((channel, name, exc))
                print(f"::warning::{channel} mail failed for {name}: {type(exc).__name__}: {exc}")
    if failures:
        for channel, name, exc in failures:
            print(f"mail failure detail: channel={channel} recipient={name} error={exc}")
        raise RuntimeError(f"V3 supplemental mail delivery failed for {len(failures)} attempt(s)")


if __name__ == "__main__":
    main()
