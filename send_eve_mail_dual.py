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
BPC_VALUE = Path("results/latest/bpc_value_opportunities.csv")
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


def finite_num(v, default=None):
    try:
        x = float(v)
        if pd.isna(x) or x == float("inf") or x == float("-inf"):
            return default
        return x
    except Exception:
        return default


def merge_rows(primary, secondary):
    out = primary.copy()
    for k, v in secondary.items():
        cur = out.get(k)
        empty = cur is None or cur == "" or (isinstance(cur, float) and pd.isna(cur))
        if empty:
            out[k] = v
    return out


def build_deal_candidates():
    out = []
    deals = read_csv(DEALS)
    if deals.empty:
        return out
    for _, r in deals.iterrows():
        cls = str(r.get("deal_class", ""))
        risk_rank = float(r.get("risk_rank", 5) or 5)
        priority = (300 if cls.startswith("A") else 200) + float(r.get("deal_score", 0) or 0) - risk_rank * 2
        out.append({"priority": priority, "contract_id": int(float(r["contract_id"])), "row": r})
    out.sort(key=lambda x: x["priority"], reverse=True)
    return out


def build_bpc_candidates():
    """Union intrinsic BPC-value deals with manufacturing deals; intrinsic value is primary."""
    best = {}

    value_df = read_csv(BPC_VALUE)
    if not value_df.empty and "contract_id" in value_df.columns:
        for _, r in value_df.iterrows():
            try:
                cid = int(float(r["contract_id"]))
            except Exception:
                continue
            priority = 500 + float(r.get("bpc_value_score", 0) or 0)
            best[cid] = {"priority": priority, "contract_id": cid, "row": r.copy(), "source": "intrinsic"}

    bpc = read_csv(BPC)
    if not bpc.empty and "contract_id" in bpc.columns:
        profit = pd.to_numeric(bpc.get("net_profit"), errors="coerce").fillna(0)
        roi = pd.to_numeric(bpc.get("net_roi"), errors="coerce").fillna(0)
        keep = (profit >= BPC_MIN_PROFIT) & (roi >= BPC_MIN_ROI)
        if "market_capacity_contracts" in bpc.columns:
            keep &= pd.to_numeric(bpc["market_capacity_contracts"], errors="coerce").fillna(0) >= 1
        if "recommendation" in bpc.columns:
            keep &= ~bpc["recommendation"].fillna("").astype(str).str.startswith("D")

        for _, r in bpc.loc[keep].iterrows():
            try:
                cid = int(float(r["contract_id"]))
            except Exception:
                continue
            priority = 300 + float(r.get("opportunity_score", 0) or 0)
            if cid in best:
                merged = merge_rows(best[cid]["row"].to_dict(), r.to_dict())
                best[cid]["row"] = pd.Series(merged)
                best[cid]["source"] = "intrinsic+manufacturing"
                best[cid]["priority"] += min(40, float(r.get("opportunity_score", 0) or 0) * 0.4)
            else:
                best[cid] = {"priority": priority, "contract_id": cid, "row": r.copy(), "source": "manufacturing"}

    out = list(best.values())
    out.sort(
        key=lambda x: (
            x["priority"],
            finite_num(x["row"].get("bpc_intrinsic_value_surplus"), 0) or 0,
            finite_num(x["row"].get("net_profit"), 0) or 0,
        ),
        reverse=True,
    )
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
    risk = html.escape(str(r.get("risk_tier", "风险未知")))
    items = html.escape(short_text(r.get("items", ""), 150))
    hidden = html.escape(short_text(r.get("top_value_items", ""), 130))
    station = html.escape(short_text(r.get("station_name", ""), 75))
    system_name = html.escape(short_text(r.get("system_name", ""), 45))
    sec = float(r.get("security", 0) or 0)
    secure_jumps = int(float(r.get("secure_jumps_to_jita", -1) or -1))
    shortest_jumps = int(float(r.get("shortest_jumps_to_jita", -1) or -1))
    jumps_text = f"安全路线 {secure_jumps}跳" if secure_jumps >= 0 else (f"最短路线约 {shortest_jumps}跳" if shortest_jumps >= 0 else "路线未知")
    cov = float(r.get("buy_unit_coverage", 0) or 0) * 100
    alliance = html.escape(short_text(r.get("friendly_alliance_ticker", ""), 20))

    if str(r.get("deal_class", "")).startswith("A"):
        profit = float(r.get("instant_net_profit", 0) or 0)
        roi = float(r.get("instant_net_roi", 0) or 0) * 100
        valuation = f"Jita即时买单 {fmt_isk(r.get('jita_buy_gross',0))} · 税 {fmt_isk(r.get('sales_tax_if_instant',0))} · 物流预留 {fmt_isk(r.get('haul_reserve',0))}"
        caveat = f"买单数量覆盖 {cov:.0f}%"
    else:
        profit = float(r.get("list_net_profit_est", 0) or 0)
        roi = float(r.get("list_net_roi_est", 0) or 0) * 100
        valuation = f"Jita挂卖参考 {fmt_isk(r.get('jita_replacement_value',0))} · Broker {fmt_isk(r.get('list_broker_fee',0))} · 税 {fmt_isk(r.get('list_sales_tax',0))} · 改价 {fmt_isk(r.get('list_relist_reserve',0))}"
        caveat = "挂单利润为估算，不等于即时可兑现"

    alliance_note = f" · 当前联盟[{alliance}]" if alliance else ""
    return (
        f"<b>{i}. {cls} · {risk}</b><br>{items}<br>"
        f"合同价 {fmt_isk(r.get('contract_price',0))} · 净利约 {fmt_isk(profit)} · 净ROI {roi:.1f}%<br>"
        f"{valuation}<br>位置 {system_name} / {station} · 安全等级 {sec:.1f} · {jumps_text}{alliance_note}<br>"
        f"{caveat}<br>"
        + (f"主要价值：{hidden}<br>" if hidden else "")
        + f"<url=contract:0//{cid}><b>打开合同</b></url><br><br>"
    )


def bpc_market_html(r):
    n = finite_num(r.get("bpc_market_sample_count"), 0) or 0
    avg = finite_num(r.get("bpc_market_avg_per_run"))
    median = finite_num(r.get("bpc_market_median_per_run"))
    current = finite_num(r.get("bpc_current_cost_per_run"))
    discount = finite_num(r.get("bpc_discount_vs_avg"))
    market_value = finite_num(r.get("bpc_contract_market_value_est"))
    surplus = finite_num(r.get("bpc_intrinsic_value_surplus"))
    basis = str(r.get("bpc_market_basis", "") or "")
    if n <= 0 or avg is None or current is None:
        return "BPC合同市场估值：暂无足够同类合同样本<br>"

    if basis.startswith("same_type_ME"):
        basis_text = "同种蓝图、同ME/TE"
    else:
        basis_text = "同种蓝图（ME/TE混合样本）"
    dev_text = f"便宜 {-discount*100:.1f}%" if discount is not None and discount < 0 else (f"偏贵 {discount*100:.1f}%" if discount is not None else "偏差未知")
    return (
        f"<b>BPC自身价值：</b>当前 {fmt_isk(current)}/流程 · 可比平均 {fmt_isk(avg)}/流程"
        + (f" · 中位 {fmt_isk(median)}/流程" if median is not None else "")
        + f" · {dev_text}<br>"
        f"按可比合同估值整包约 {fmt_isk(market_value)} · 价值差 {fmt_isk(surplus)} · 样本{int(n)}个（{basis_text}）<br>"
    )


def bpc_location_html(r):
    system_name = short_text(r.get("system_name", ""), 45)
    station = short_text(r.get("station_name", ""), 70)
    risk = short_text(r.get("risk_tier", ""), 40)
    if not system_name and not station:
        return ""
    sec = finite_num(r.get("security"))
    jumps = finite_num(r.get("shortest_jumps_to_jita"))
    bits = []
    if system_name:
        bits.append(html.escape(system_name))
    if station:
        bits.append(html.escape(station))
    if sec is not None:
        bits.append(f"安全等级 {sec:.1f}")
    if jumps is not None and jumps >= 0:
        bits.append(f"Jita最短 {int(jumps)}跳")
    if risk:
        bits.append(html.escape(risk))
    return "位置 " + " · ".join(bits) + "<br>"


def bpc_html(i, r):
    cid = int(float(r["contract_id"]))
    bp_name = short_text(r.get("blueprint_name", ""), 110)
    if not bp_name:
        bp_name = short_text(r.get("blueprints", ""), 110)
    if not bp_name:
        bp_name = short_text(r.get("products", "Unknown BPC"), 110)
    bp_name = html.escape(bp_name)

    total_runs = finite_num(r.get("total_bpc_runs"))
    copies = finite_num(r.get("bpc_copy_count"))
    run_note = ""
    if total_runs is not None:
        run_note = f" · 总流程 {int(total_runs)}"
        if copies is not None:
            run_note += f" · {int(copies)}张"

    lines = [
        f"<b>{i}. {bp_name}</b>{run_note}<br>",
        f"合同价 {fmt_isk(r.get('contract_price',0))}<br>",
        bpc_market_html(r),
    ]

    mfg_profit = finite_num(r.get("net_profit"))
    mfg_roi = finite_num(r.get("net_roi"))
    if mfg_profit is not None and mfg_roi is not None:
        cap = finite_num(r.get("market_capacity_contracts"), 0) or 0
        lines.append(
            f"制造参考：全成本净利 {fmt_isk(mfg_profit)} · 净ROI {mfg_roi*100:.1f}% · 买盘容量 {cap:.0f}批<br>"
        )
        lines.append(
            f"材料 {fmt_isk(r.get('material_cost_jita_depth',0))} · 制造 {fmt_isk(r.get('manufacturing_job_cost',0))} · "
            f"Broker {fmt_isk(r.get('market_broker_fee',0))} · 税 {fmt_isk(r.get('sales_tax',0))} · "
            f"改价 {fmt_isk(r.get('relist_cost_reserve',0))} · 物流 {fmt_isk(r.get('configured_haul_cost',0))}<br>"
        )
    else:
        lines.append("制造参考：未进入当前制造强机会榜；不影响蓝图自身低估判断。<br>")

    lines.append(bpc_location_html(r))
    lines.append(f"<url=contract:0//{cid}><b>打开合同</b></url><br><br>")
    return "".join(lines)


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
            "全星域扫描。风险分层：A1联盟势力范围、A2 Jita近郊高安、B其他高安、C低安、D非友军00/未知建筑。"
        )
    else:
        subject = f"现货合同捡漏 {stamp} · TOP{len(picked)}"
        parts = [
            f"<b>单件/多件现货合同捡漏 TOP{len(picked)}</b><br>{stamp}<br>",
            f"全星域合格候选 {len(candidates)} · 发送前剔除 {removed} 个失效/不可见合同。<br>",
            "风险：A1联盟势力范围低风险 ＞ A2 Jita近郊高安 ＞ B其他高安 ＞ C低安 ＞ D非友军00/未知。<br>"
            "经济排序：即时买单套利优先，其次挂单潜在套利。<br><br>",
        ]
        for i, c in enumerate(picked, 1):
            parts.append(deal_html(i, c["row"]))
        parts.append("说明：风险标签不代表绝对安全；00/低安运输仍需根据实时路况、营地和建筑访问权限复核。现货捡漏不与BPC混排。")
        body = "".join(parts)
    send_mail(recipient_id, subject, body, "spot-deals")


def send_bpc_digest(recipient_id, stamp):
    candidates = build_bpc_candidates()
    picked, removed = live_pick(candidates)
    if not picked:
        subject = f"BPC蓝图捡漏 {stamp} · 暂无现存强机会"
        body = (
            f"<b>BPC蓝图捡漏</b><br>{stamp}<br><br>"
            f"候选 {len(candidates)} 个；发送前剔除/不可见 {removed} 个；当前没有仍存活的强机会。<br><br>"
            "主筛选看同种BPC每流程合同价格是否显著低于可比平均/中位价；制造利润是第二参考。地点不限高安，低安和00只做风险标记。"
        )
    else:
        subject = f"BPC蓝图捡漏 {stamp} · TOP{len(picked)}"
        parts = [
            f"<b>BPC蓝图捡漏 TOP{len(picked)}</b><br>{stamp}<br>",
            f"全星域候选 {len(candidates)} · 发送前剔除 {removed} 个失效/不可见合同。<br>",
            "主排序：蓝图自身每流程价格相对同类平均/中位价的显著折价；制造后全成本利润作为第二参考。<br>"
            "地点不限高安：低安/00可进入候选；真正无法解析或星门不可达的地点才剔除。<br><br>",
        ]
        for i, c in enumerate(picked, 1):
            parts.append(bpc_html(i, c["row"]))
        parts.append("说明：可比均价会剔除极端离谱挂价，并用中位价做防误判校验；合同挂牌价不等于历史真实成交价。玩家建筑仍需核对停靠权限。")
        body = "".join(parts)
    send_mail(recipient_id, subject, body, "bpc-value")


def main():
    if not API_KEY:
        raise RuntimeError("Missing EVE_MAIL_API_KEY")
    recipient_id = resolve_character(RECIPIENT_NAME)
    stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")
    send_deal_digest(recipient_id, stamp)
    send_bpc_digest(recipient_id, stamp)


if __name__ == "__main__":
    main()
