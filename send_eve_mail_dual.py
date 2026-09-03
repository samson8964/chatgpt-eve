import hashlib
import html
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

from send_eve_mail_fast import fmt_isk, resolve_character, contract_is_live

DEALS = Path("results/latest/contract_deals.csv")
BPC = Path("results/latest/ranked_opportunities.csv")
WORKER = os.getenv("EVE_MAIL_WORKER_URL", "https://eve-contract-opener.99617224.workers.dev").rstrip("/")
API_KEY = os.getenv("EVE_MAIL_API_KEY", "").strip()
RECIPIENT_NAME = os.getenv("EVE_MAIL_RECIPIENT_NAME", "MikeChong").strip()
MAIL_TOP = int(os.getenv("MAIL_TOP", "10"))
LIVE_POOL = int(os.getenv("MAIL_LIVE_POOL", "60"))
LIVE_WORKERS = int(os.getenv("LIVE_CHECK_WORKERS", "10"))
BPC_MIN_PROFIT = float(os.getenv("MAIL_MIN_NET_PROFIT", "10000000"))
BPC_MIN_ROI = float(os.getenv("MAIL_MIN_NET_ROI", "0.08"))


def read_csv(path):
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def short_text(v, n=145):
    s = " ".join(str(v or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def build_deal_candidates():
    out = []
    deals = read_csv(DEALS)
    if deals.empty:
        return out
    for _, r in deals.iterrows():
        cls = str(r.get("deal_class", ""))
        priority = (300 if cls.startswith("A") else 200) + float(r.get("deal_score", 0) or 0)
        out.append({"priority": priority, "contract_id": int(float(r["contract_id"])), "row": r})
    out.sort(key=lambda x: x["priority"], reverse=True)
    return out


def build_bpc_candidates():
    out = []
    bpc = read_csv(BPC)
    if bpc.empty:
        return out
    profit = pd.to_numeric(bpc.get("net_profit"), errors="coerce").fillna(0)
    roi = pd.to_numeric(bpc.get("net_roi"), errors="coerce").fillna(0)
    keep = (profit >= BPC_MIN_PROFIT) & (roi >= BPC_MIN_ROI)
    if "market_capacity_contracts" in bpc.columns:
        keep &= pd.to_numeric(bpc["market_capacity_contracts"], errors="coerce").fillna(0) >= 1
    if "recommendation" in bpc.columns:
        keep &= ~bpc["recommendation"].fillna("").astype(str).str.startswith("D")
    for _, r in bpc.loc[keep].iterrows():
        out.append({"priority": float(r.get("opportunity_score", 0) or 0), "contract_id": int(float(r["contract_id"])), "row": r})
    out.sort(key=lambda x: (x["priority"], float(x["row"].get("net_profit", 0) or 0)), reverse=True)
    return out


def live_pick(candidates):
    pool = candidates[: max(MAIL_TOP, LIVE_POOL)]
    if not pool:
        return [], 0
    states = {}
    with ThreadPoolExecutor(max_workers=min(LIVE_WORKERS, len(pool))) as ex:
        futs = {ex.submit(contract_is_live, c["contract_id"]): i for i, c in enumerate(pool)}
        for fut in as_completed(futs):
            i = futs[fut]
            try:
                states[i] = bool(fut.result())
            except Exception:
                states[i] = False
    live = [c for i, c in enumerate(pool) if states.get(i, False)]
    return live[:MAIL_TOP], len(pool) - len(live)


def deal_html(i, r):
    cid = int(float(r["contract_id"]))
    cls = html.escape(str(r.get("deal_class", "合同捡漏")))
    items = html.escape(short_text(r.get("items", ""), 150))
    hidden = html.escape(short_text(r.get("top_value_items", ""), 130))
    jumps = int(float(r.get("secure_jumps_to_jita", 0) or 0))
    station = html.escape(short_text(r.get("station_name", ""), 75))
    cov = float(r.get("buy_unit_coverage", 0) or 0) * 100
    if str(r.get("deal_class", "")).startswith("A"):
        profit = float(r.get("instant_net_profit", 0) or 0)
        roi = float(r.get("instant_net_roi", 0) or 0) * 100
        valuation = f"Jita即时买单 {fmt_isk(r.get('jita_buy_gross',0))} · 税 {fmt_isk(r.get('sales_tax_if_instant',0))} · 物流 {fmt_isk(r.get('haul_reserve',0))}"
        caveat = f"买单数量覆盖 {cov:.0f}%"
    else:
        profit = float(r.get("list_net_profit_est", 0) or 0)
        roi = float(r.get("list_net_roi_est", 0) or 0) * 100
        valuation = f"Jita挂卖参考 {fmt_isk(r.get('jita_replacement_value',0))} · Broker {fmt_isk(r.get('list_broker_fee',0))} · 税 {fmt_isk(r.get('list_sales_tax',0))} · 改价 {fmt_isk(r.get('list_relist_reserve',0))}"
        caveat = "挂单利润为估算，不等于即时可兑现"
    return (
        f"<b>{i}. {cls}</b><br>{items}<br>"
        f"合同价 {fmt_isk(r.get('contract_price',0))} · 净利约 {fmt_isk(profit)} · 净ROI {roi:.1f}%<br>"
        f"{valuation}<br>位置 {station} · 安全路线 {jumps}跳 · {caveat}<br>"
        + (f"主要价值：{hidden}<br>" if hidden else "")
        + f"<url=contract:0//{cid}><b>打开合同</b></url><br><br>"
    )


def bpc_html(i, r):
    cid = int(float(r["contract_id"]))
    product = html.escape(short_text(r.get("products", "Unknown"), 120))
    roi = float(r.get("net_roi", 0) or 0) * 100
    cap = float(r.get("market_capacity_contracts", 0) or 0)
    return (
        f"<b>{i}. {product}</b><br>"
        f"合同价 {fmt_isk(r.get('contract_price',0))} · 全成本净利 {fmt_isk(r.get('net_profit',0))} · 净ROI {roi:.1f}% · 买盘容量 {cap:.0f}批<br>"
        f"材料 {fmt_isk(r.get('material_cost_jita_depth',0))} · 制造 {fmt_isk(r.get('manufacturing_job_cost',0))} · Broker {fmt_isk(r.get('market_broker_fee',0))} · 税 {fmt_isk(r.get('sales_tax',0))} · 改价 {fmt_isk(r.get('relist_cost_reserve',0))} · 物流 {fmt_isk(r.get('configured_haul_cost',0))}<br>"
        f"<url=contract:0//{cid}><b>打开合同</b></url><br><br>"
    )


def send_mail(recipient_id, subject, body, channel_key):
    if len(body) > 7900:
        body = body[:7700] + "<br><br>正文过长，已截断；优先显示排名靠前机会。"
    digest = hashlib.sha256((channel_key + subject + body + str(recipient_id)).encode()).hexdigest()[:32]
    r = requests.post(
        f"{WORKER}/api/send-mail",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"recipient_id": recipient_id, "subject": subject, "body": body, "idempotency_key": digest},
        timeout=30,
    )
    print(f"{channel_key} mail worker: HTTP {r.status_code} {r.text[:500]}")
    r.raise_for_status()


def send_deal_digest(recipient_id, stamp):
    candidates = build_deal_candidates()
    picked, removed = live_pick(candidates)
    if not picked:
        subject = f"现货合同捡漏 {stamp} · 暂无现存强机会"
        body = (
            f"<b>单件/多件现货合同捡漏</b><br>{stamp}<br><br>"
            f"合格候选 {len(candidates)} 个；发送前剔除/不可见 {removed} 个；当前没有仍存活的强机会。<br><br>"
            "A类按Jita当前买单即时兑现；B类按Jita挂卖参考价扣Broker、销售税、改价和物流预留。"
        )
    else:
        subject = f"现货合同捡漏 {stamp} · TOP{len(picked)}"
        parts = [
            f"<b>单件/多件现货合同捡漏 TOP{len(picked)}</b><br>{stamp}<br>",
            f"合格候选 {len(candidates)} · 发送前剔除 {removed} 个失效/不可见合同。<br>",
            "排序：A即时买单套利优先，其次B挂单潜在套利。<br><br>",
        ]
        for i, c in enumerate(picked, 1):
            parts.append(deal_html(i, c["row"]))
        parts.append("说明：现货捡漏不与BPC制造混排；下单前仍打开合同核对物品、数量和地点。")
        body = "".join(parts)
    send_mail(recipient_id, subject, body, "spot-deals")


def send_bpc_digest(recipient_id, stamp):
    candidates = build_bpc_candidates()
    picked, removed = live_pick(candidates)
    if not picked:
        subject = f"蓝图制造捡漏 {stamp} · 暂无现存强机会"
        body = (
            f"<b>BPC蓝图制造捡漏</b><br>{stamp}<br><br>"
            f"全成本合格候选 {len(candidates)} 个；发送前剔除/不可见 {removed} 个；当前没有仍存活的强机会。<br><br>"
            f"筛选门槛：净利润≥{fmt_isk(BPC_MIN_PROFIT)}、净ROI≥{BPC_MIN_ROI*100:.0f}%、买盘容量≥1批。"
        )
    else:
        subject = f"蓝图制造捡漏 {stamp} · TOP{len(picked)}"
        parts = [
            f"<b>BPC蓝图制造捡漏 TOP{len(picked)}</b><br>{stamp}<br>",
            f"全成本合格候选 {len(candidates)} · 发送前剔除 {removed} 个失效/不可见合同。<br>",
            "利润口径：BPC + 材料 + 制造安装费(含SCI/设施税/SCC) + Broker + 销售税 + 改价预留 + 物流。<br><br>",
        ]
        for i, c in enumerate(picked, 1):
            parts.append(bpc_html(i, c["row"]))
        parts.append("说明：BPC制造机会不与现货合同混排；SCC已包含在制造安装费中，不重复扣。")
        body = "".join(parts)
    send_mail(recipient_id, subject, body, "bpc-manufacturing")


def main():
    if not API_KEY:
        raise RuntimeError("Missing EVE_MAIL_API_KEY")
    recipient_id = resolve_character(RECIPIENT_NAME)
    stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")

    # Two intentionally separate mails, each independently ranked and live-checked.
    send_deal_digest(recipient_id, stamp)
    send_bpc_digest(recipient_id, stamp)


if __name__ == "__main__":
    main()
