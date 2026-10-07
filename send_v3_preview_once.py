from __future__ import annotations

import html
import os
from pathlib import Path

import pandas as pd

from send_eve_mail_dual import send_mail
from send_eve_mail_fast import contract_is_live, fmt_isk, resolve_character

RESULT = Path("results/latest/v3_four_h_contracts.csv")
TARGET = int(os.getenv("V3_PREVIEW_CONTRACT_ID", "236775678"))
RECIPIENT = os.getenv("EVE_MAIL_RECIPIENT_NAME", "MikeChong").strip() or "MikeChong"


def _num(v, default=0.0):
    try:
        x = float(v)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _text(v, default=""):
    s = str(v if v is not None else "").strip()
    if not s or s.lower() in {"nan", "none"}:
        return default
    return s


def main():
    if not RESULT.exists():
        raise RuntimeError(f"Missing V3 result: {RESULT}")

    df = pd.read_csv(RESULT)
    if df.empty or "contract_id" not in df.columns:
        raise RuntimeError("V3 4-H result is empty or malformed")

    ids = pd.to_numeric(df["contract_id"], errors="coerce").fillna(0).astype(int)
    rows = df.loc[ids.eq(TARGET)]
    if rows.empty:
        raise RuntimeError(f"Target V3 opportunity {TARGET} not found in current 4-H results")

    r = rows.iloc[0]
    if "mail_eligible" in rows.columns:
        eligible = str(r.get("mail_eligible", "")).strip().lower() in {"1", "true", "t", "yes", "y"}
        if not eligible:
            raise RuntimeError(f"Target {TARGET} is no longer mail-eligible")

    if not contract_is_live(TARGET):
        raise RuntimeError(f"Target contract {TARGET} is no longer live")

    recipient_id = resolve_character(RECIPIENT)
    stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")

    source = html.escape(_text(r.get("source_label"), "4-HWWF"))
    exit_market = html.escape(_text(r.get("exit_market"), "Jita 4-4 buy"))
    items = html.escape(_text(r.get("items"), ""))
    grade = html.escape(_text(r.get("score_grade"), "-"))
    confidence = html.escape(_text(r.get("confidence_class"), "-"))
    reason = html.escape(_text(r.get("policy_reason"), "-"))

    subject = f"V3测试机会 {stamp} · 4-H合同 {TARGET}"
    body = (
        f"<b>Opportunity Engine V3 实际邮件预览</b><br>{stamp}<br><br>"
        f"<b>[{grade}] 合同 {TARGET}</b><br>"
        f"来源：{source}<br>"
        f"退出：{exit_market}<br>"
        f"合同价：{fmt_isk(r.get('contract_price', r.get('source_cost', 0)))}<br>"
        f"可兑现价值：{fmt_isk(r.get('cash_floor_gross', r.get('destination_value', 0)))}<br>"
        f"<b>验证净利润：{fmt_isk(r.get('net_profit', 0))}</b> · ROI {_num(r.get('net_roi')):.1%}<br>"
        f"压力净利润：{fmt_isk(r.get('stress_net_profit', 0))}<br>"
        f"利润密度：{_num(r.get('profit_per_m3')):,.0f} ISK/m³<br>"
        f"现金覆盖：{_num(r.get('cash_floor_coverage', r.get('coverage'))):.1%}<br>"
        f"置信：{confidence} · 判定：{reason}<br><br>"
        f"主要物品：{items}<br><br>"
        f"<url=contract:0//{TARGET}><b>打开合同</b></url><br><br>"
        "这是V3切换后的实质邮件测试。下单前仍请在游戏内核对合同内容、位置与实时买盘。"
    )

    send_mail(recipient_id, subject, body, "v3-preview-once")
    print(f"V3 preview mail sent to {RECIPIENT} ({recipient_id}) for contract {TARGET}")


if __name__ == "__main__":
    main()
