from __future__ import annotations

import html
import os
import re
import time
from pathlib import Path

import pandas as pd
import requests

from mail_profit_policy import MAIL_MIN_VERIFIED_NET_PROFIT
from send_eve_mail_dual import send_mail
from send_eve_mail_fast import contract_is_live, fmt_isk, resolve_character

LATEST = Path("results/latest")
STATE = Path("results/state")
MAIL_TOP = int(os.getenv("MAIL_TOP", "10"))
POLICY_VERSION = "opportunity-v3-production-2026-10-07"
RESEND_ABS_PROFIT = float(os.getenv("MAIL_RESEND_ABS_PROFIT", "20000000"))
RESEND_REL_PROFIT = float(os.getenv("MAIL_RESEND_REL_PROFIT", "0.10"))
RESEND_ROI_DELTA = float(os.getenv("MAIL_RESEND_ROI_DELTA", "0.02"))
REMIND_AFTER_HOURS = float(os.getenv("MAIL_REMIND_AFTER_HOURS", "6"))

CHANNELS = {
    "v3-full-cash": {
        "path": LATEST / "v3_full_cash.csv",
        "id_col": "contract_id",
        "title": "V3完整现金套利",
        "kind": "contract",
    },
    "v3-cash-floor": {
        "path": LATEST / "v3_cash_floor.csv",
        "id_col": "contract_id",
        "title": "V3现金底价捡漏",
        "kind": "contract",
    },
    "v3-barter": {
        "path": LATEST / "v3_barter.csv",
        "id_col": "contract_id",
        "title": "V3以物换物捡漏",
        "kind": "contract",
    },
    "v3-conservative-list": {
        "path": LATEST / "v3_conservative_listing.csv",
        "id_col": "contract_id",
        "title": "V3保守挂卖观察",
        "kind": "contract",
    },
    "v3-four-h-contract": {
        "path": LATEST / "v3_four_h_contracts.csv",
        "id_col": "contract_id",
        "title": "V3 4-H合同捡漏",
        "kind": "structure-contract",
    },
    "v3-cj-contract": {
        "path": LATEST / "v3_cj_contracts.csv",
        "id_col": "contract_id",
        "title": "V3 C-J合同捡漏",
        "kind": "structure-contract",
    },
    "v3-amarr-to-jita": {
        "path": LATEST / "v3_amarr_to_jita.csv",
        "id_col": "type_id",
        "title": "V3 Amarr采购→Jita",
        "kind": "source-market",
    },
    "v3-dodixie-to-jita": {
        "path": LATEST / "v3_dodixie_to_jita.csv",
        "id_col": "type_id",
        "title": "V3 Dodixie采购→Jita",
        "kind": "source-market",
    },
    "v3-four-h-to-jita": {
        "path": LATEST / "v3_four_h_to_jita.csv",
        "id_col": "type_id",
        "title": "V3 4-H采购→Jita",
        "kind": "source-market",
    },
    "v3-cj-to-jita": {
        "path": LATEST / "v3_cj_to_jita.csv",
        "id_col": "type_id",
        "title": "V3 C-J采购→Jita",
        "kind": "source-market",
    },
    "v3-jita-to-4h": {
        "path": LATEST / "v3_jita_to_four_h.csv",
        "id_col": "type_id",
        "title": "V3 Jita→4-H套利",
        "kind": "reverse-market",
    },
    "v3-bpc": {
        "path": LATEST / "v3_bpc_opportunities.csv",
        "id_col": "contract_id",
        "title": "V3 BPC制造捡漏",
        "kind": "bpc",
    },
}


def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
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
    if v is None:
        return default
    s = str(v).strip()
    if not s or s.lower() in {"nan", "none"}:
        return default
    return s


def recipient_names():
    raw = os.getenv("EVE_MAIL_RECIPIENT_NAMES", "").strip()
    if raw:
        names = [x.strip() for x in raw.split(",") if x.strip()]
    else:
        names = [os.getenv("EVE_MAIL_RECIPIENT_NAME", "MikeChong").strip() or "MikeChong"]
    return list(dict.fromkeys(names))


def enabled_channels():
    raw = os.getenv("V3_CHANNELS", "").strip()
    if not raw:
        return list(CHANNELS)
    wanted = [x.strip() for x in raw.split(",") if x.strip()]
    unknown = [x for x in wanted if x not in CHANNELS]
    if unknown:
        raise RuntimeError(f"Unknown V3 channel(s): {','.join(unknown)}")
    return wanted


def safe_key(name: str):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "recipient"


def state_path(channel: str, recipient: str):
    return STATE / f"mail_last_{channel}_{safe_key(recipient)}.csv"


def build_candidates(channel: str):
    cfg = CHANNELS[channel]
    df = _read(cfg["path"])
    if df.empty or cfg["id_col"] not in df.columns:
        return []

    if "mail_eligible" in df.columns:
        df = df[df["mail_eligible"].fillna(False).astype(str).str.lower().isin({"1", "true", "t", "yes", "y"})].copy()
    elif "execution_status" in df.columns:
        df = df[df["execution_status"].fillna("").astype(str).str.upper().eq("SAFE")].copy()
    if df.empty:
        return []

    profit = pd.to_numeric(df.get("net_profit"), errors="coerce").fillna(0.0)
    roi = pd.to_numeric(df.get("net_roi"), errors="coerce").fillna(0.0)
    score = pd.to_numeric(df.get("opportunity_score"), errors="coerce").fillna(0.0)
    df = df.assign(_profit=profit, _roi=roi, _score=score)
    df = df[(df["_profit"] >= MAIL_MIN_VERIFIED_NET_PROFIT) & (df["_roi"] > 0)].copy()
    df.sort_values(["_score", "_profit", "_roi"], ascending=False, inplace=True)

    out = []
    needs_live_contract = cfg["kind"] in {"contract", "structure-contract", "bpc"}
    candidate_limit = MAIL_TOP * 3 if needs_live_contract else MAIL_TOP
    for _, r in df.head(candidate_limit).iterrows():
        try:
            ident = int(float(r[cfg["id_col"]]))
        except Exception:
            continue

        if needs_live_contract:
            try:
                if not contract_is_live(ident):
                    print(f"{channel}: skip stale contract {ident}")
                    continue
            except Exception as exc:
                print(f"{channel}: live check failed closed for {ident}: {type(exc).__name__}: {exc}")
                continue

        out.append(
            {
                "id": ident,
                "profit": float(r["_profit"]),
                "roi": float(r["_roi"]),
                "score": float(r["_score"]),
                "grade": _text(r.get("score_grade")),
                "row": r,
            }
        )
        if len(out) >= MAIL_TOP:
            break
    return out


def should_suppress(channel: str, recipient: str, picked):
    path = state_path(channel, recipient)
    if not path.exists():
        return not picked
    old = _read(path)
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
        print(f"{channel} trigger: TOP membership changed")
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
            return False
        if abs(cur["roi"] - _num(prev.get("roi"))) >= RESEND_ROI_DELTA:
            return False
        if cur["grade"] != _text(prev.get("grade")):
            return False

    sent = pd.to_datetime(old["sent_at"], utc=True, errors="coerce").dropna()
    if sent.empty:
        return False
    age_h = (pd.Timestamp.now(tz="UTC") - sent.max()).total_seconds() / 3600.0
    return age_h < REMIND_AFTER_HOURS


def save_state(channel: str, recipient: str, picked):
    path = state_path(channel, recipient)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = pd.Timestamp.now(tz="UTC").isoformat()
    rows = []
    for rank, c in enumerate(picked, 1):
        rows.append(
            {
                "policy_version": POLICY_VERSION,
                "rank": rank,
                "id": c["id"],
                "profit": c["profit"],
                "roi": c["roi"],
                "grade": c["grade"],
                "sent_at": now,
            }
        )
    pd.DataFrame(rows, columns=["policy_version", "rank", "id", "profit", "roi", "grade", "sent_at"]).to_csv(path, index=False)


def _loc(r):
    system = html.escape(_text(r.get("system_name"), "未知"))
    station = html.escape(_text(r.get("station_name"), ""))
    jumps = int(_num(r.get("shortest_jumps_to_jita"), -1))
    risk = html.escape(_text(r.get("risk_tier"), ""))
    bits = [system]
    if station:
        bits.append(station)
    if jumps >= 0:
        bits.append(f"Jita {jumps}跳")
    if risk:
        bits.append(risk)
    return " · ".join(bits)


def _render_public_contract(i, c, r):
    return (
        f"<b>{i}. [{html.escape(c['grade'] or '-')}] 合同 {c['id']}</b><br>"
        f"净利 {fmt_isk(c['profit'])} · ROI {c['roi']:.1%} · 压力净利 {fmt_isk(r.get('stress_net_profit',0))}<br>"
        f"当前可兑现 {fmt_isk(r.get('cash_floor_gross', r.get('destination_value',0)))} · "
        f"覆盖 {100*_num(r.get('cash_floor_coverage', r.get('coverage'))):.0f}% · "
        f"置信 {html.escape(_text(r.get('confidence_class'), '-'))}<br>"
        f"{html.escape(_text(r.get('cash_items', r.get('items',''))))}<br>{_loc(r)}<br>"
        f"<url=contract:0//{c['id']}><b>打开合同</b></url><br><br>"
    )


def _render_structure_contract(i, c, r):
    source = html.escape(_text(r.get("source_label"), "-"))
    exit_market = html.escape(_text(r.get("exit_market"), "Jita 4-4 buy"))
    return (
        f"<b>{i}. [{html.escape(c['grade'] or '-')}] 合同 {c['id']}</b><br>"
        f"来源 {source} · 退出 {exit_market}<br>"
        f"合同价 {fmt_isk(r.get('contract_price', r.get('source_cost',0)))} · "
        f"净利 {fmt_isk(c['profit'])} · ROI {c['roi']:.1%}<br>"
        f"压力净利 {fmt_isk(r.get('stress_net_profit',0))} · "
        f"利润密度 {_num(r.get('profit_per_m3')):,.0f} ISK/m³ · "
        f"现金覆盖 {_num(r.get('cash_floor_coverage', r.get('coverage'))):.1%}<br>"
        f"{html.escape(_text(r.get('items')))}<br>"
        f"<url=contract:0//{c['id']}><b>打开合同</b></url><br><br>"
    )


def _render_source_market(i, c, r):
    tid = int(c["id"])
    source = html.escape(_text(r.get("source_label"), "-"))
    item = html.escape(_text(r.get("item_name"), str(tid)))
    return (
        f"<b>{i}. [{html.escape(c['grade'] or '-')}] {item}</b><br>"
        f"{source}采购 → Jita 4-4买单兑现<br>"
        f"数量 {int(_num(r.get('quantity'))):,} · 源卖价 {fmt_isk(r.get('source_best_sell',0))}/件 · "
        f"Jita买价 {fmt_isk(r.get('jita_best_buy',0))}/件<br>"
        f"净利 {fmt_isk(c['profit'])} · ROI {c['roi']:.1%} · "
        f"压力净利 {fmt_isk(r.get('stress_net_profit',0))} · 物流预留 {fmt_isk(r.get('haul_cost',0))}<br>"
        f"<url=showinfo:{tid}><b>查看物品</b></url><br><br>"
    )


def _render_reverse_market(i, c, r):
    tid = int(c["id"])
    return (
        f"<b>{i}. [{html.escape(c['grade'] or '-')}] {html.escape(_text(r.get('item_name'), str(tid)))}</b><br>"
        f"数量 {int(_num(r.get('quantity'))):,} · 净利 {fmt_isk(c['profit'])} · ROI {c['roi']:.1%}<br>"
        f"Jita买入 {fmt_isk(r.get('jita_best_sell',0))}/件 → 4-H买单 {fmt_isk(r.get('four_h_best_buy',0))}/件<br>"
        f"物流预留 {fmt_isk(r.get('haul_cost',0))} · 压力净利 {fmt_isk(r.get('stress_net_profit',0))}<br>"
        f"<url=showinfo:{tid}><b>查看物品</b></url><br><br>"
    )


def _render_bpc(i, c, r):
    products = html.escape(_text(r.get("products"), "BPC制造机会"))
    blueprints = html.escape(_text(r.get("blueprints"), ""))
    return (
        f"<b>{i}. [{html.escape(c['grade'] or '-')}] {products}</b><br>"
        f"合同 {c['id']} · 合同价 {fmt_isk(r.get('contract_price',0))}<br>"
        f"<b>Jita保守制造净利 {fmt_isk(c['profit'])}</b> · ROI {c['roi']:.1%} · "
        f"压力净利 {fmt_isk(r.get('stress_net_profit',0))}<br>"
        f"材料 {fmt_isk(r.get('material_cost',0))} · Jita制造费 {fmt_isk(r.get('jita_manufacturing_job_cost',0))} · "
        f"预计清算 {_num(r.get('estimated_fill_days')):.2f}天<br>"
        f"成品VWAP {fmt_isk(r.get('product_vwap',0))} · 成品滑点 {_num(r.get('product_slippage')):.2%} · "
        f"材料最大滑点 {_num(r.get('material_max_slippage')):.2%}<br>"
        f"{blueprints}<br>"
        f"<url=contract:0//{c['id']}><b>打开合同</b></url><br><br>"
    )


def render(channel: str, stamp: str, picked):
    cfg = CHANNELS[channel]
    subject = f"{cfg['title']} {stamp} · TOP{len(picked)}"
    if not picked:
        return subject, f"<b>{cfg['title']}</b><br>{stamp}<br><br>当前没有正式可推送机会。"

    parts = [f"<b>{cfg['title']} · Opportunity Engine V3 · TOP{len(picked)}</b><br>{stamp}<br><br>"]
    for i, c in enumerate(picked, 1):
        r = c["row"]
        kind = cfg["kind"]
        if channel == "v3-barter":
            parts.append(
                f"<b>{i}. [{html.escape(c['grade'] or '-')}] 合同 {c['id']}</b><br>"
                f"净利 {fmt_isk(c['profit'])} · ROI {c['roi']:.1%} · 压力净利 {fmt_isk(r.get('stress_net_profit',0))}<br>"
                f"需提供物品采购 {fmt_isk(r.get('requested_purchase_cost',0))} · "
                f"收到物品当前兑现 {fmt_isk(r.get('cash_floor_gross',0))}<br>"
                f"提供：{html.escape(_text(r.get('provide_items')))}<br>"
                f"收到：{html.escape(_text(r.get('receive_items')))}<br>{_loc(r)}<br>"
                f"<url=contract:0//{c['id']}><b>打开合同</b></url><br><br>"
            )
        elif channel == "v3-conservative-list":
            parts.append(
                f"<b>{i}. [{html.escape(c['grade'] or '-')}] 合同 {c['id']}</b><br>"
                f"净利估算 {fmt_isk(c['profit'])} · ROI {c['roi']:.1%} · "
                f"额外压力净利 {fmt_isk(r.get('stress_net_profit',0))}<br>"
                f"保守挂卖总值 {fmt_isk(r.get('conservative_gross',0))} · "
                f"预计消化 {_num(r.get('estimated_fill_days')):.1f}天<br>"
                f"{html.escape(_text(r.get('items')))}<br>{_loc(r)}<br>"
                f"<url=contract:0//{c['id']}><b>打开合同</b></url><br><br>"
            )
        elif kind == "structure-contract":
            parts.append(_render_structure_contract(i, c, r))
        elif kind == "source-market":
            parts.append(_render_source_market(i, c, r))
        elif kind == "reverse-market":
            parts.append(_render_reverse_market(i, c, r))
        elif kind == "bpc":
            parts.append(_render_bpc(i, c, r))
        else:
            parts.append(_render_public_contract(i, c, r))
    return subject, "".join(parts)


def send_with_retry(recipient_id, subject, body, channel, name):
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

    for channel in enabled_channels():
        picked = build_candidates(channel)
        print(f"{channel}: formal candidates={len(picked)}")
        for name, rid in recipients:
            if should_suppress(channel, name, picked):
                print(f"{channel} skipped for {name}: no material change TOP{len(picked)}")
                continue
            subject, body = render(channel, stamp, picked)
            try:
                send_with_retry(rid, subject, body, channel, name)
                save_state(channel, name, picked)
            except Exception as exc:
                failures.append((channel, name, exc))
                print(f"::warning::{channel} mail failed for {name}: {type(exc).__name__}: {exc}")

    if failures:
        for channel, name, exc in failures:
            print(f"mail failure detail: channel={channel} recipient={name} error={exc}")
        raise RuntimeError(f"V3 mail delivery failed for {len(failures)} channel/recipient attempt(s)")


if __name__ == "__main__":
    main()
