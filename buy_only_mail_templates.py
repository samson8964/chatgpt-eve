from __future__ import annotations

import html

from send_eve_mail_fast import fmt_isk


def _num(v, default=0.0):
    try:
        x = float(v)
        return x if x == x and x not in (float("inf"), float("-inf")) else default
    except Exception:
        return default


def _short(v, n=160):
    s = " ".join(str(v or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def deal_html(i, r):
    cid = int(float(r["contract_id"]))
    items = html.escape(_short(r.get("items", ""), 190))
    top = html.escape(_short(r.get("top_value_items", ""), 260))
    risk = html.escape(_short(r.get("risk_tier", "风险未知"), 45))
    system = html.escape(_short(r.get("system_name", ""), 45))
    station = html.escape(_short(r.get("station_name", ""), 80))
    sec = _num(r.get("security"), 0.0)
    jumps = int(_num(r.get("shortest_jumps_to_jita"), -1))
    coverage = _num(r.get("buy_unit_coverage"), 0.0) * 100
    profit = _num(r.get("instant_net_profit"), 0.0)
    roi = _num(r.get("instant_net_roi"), 0.0) * 100
    stress = _num(r.get("stress_net_profit"), 0.0)
    skin = _num(r.get("skin_value_share"), 0.0) * 100
    return (
        f"<b>{i}. 【Jita买单即时兑现】 · {risk}</b><br>"
        f"{items}<br>"
        f"合同价 {fmt_isk(r.get('contract_price',0))} · <b>净利润 {fmt_isk(profit)}</b> · ROI {roi:.1f}%<br>"
        f"Jita买单毛值 {fmt_isk(r.get('jita_buy_gross',0))} · 销售税 {fmt_isk(r.get('sales_tax_if_instant',0))} · 运输预留 {fmt_isk(r.get('haul_reserve',0))}<br>"
        f"买单数量覆盖 {coverage:.1f}% · 删除各物品最佳一档买单后压力利润 {fmt_isk(stress)}<br>"
        f"SKIN/SKINR价值占比 {skin:.1f}%（≥50%已在扫描阶段剔除）<br>"
        f"位置 {system} / {station} · 安全 {sec:.1f} · Jita最短 {jumps if jumps >= 0 else '未知'}跳<br>"
        + (f"主要买单价值：{top}<br>" if top else "")
        + f"<url=contract:0//{cid}><b>打开合同</b></url><br><br>"
    )


def _bpc_market_html(r):
    n = int(_num(r.get("bpc_market_sample_count"), 0))
    if n <= 0:
        return ""
    current = _num(r.get("bpc_current_cost_per_run"), 0.0)
    avg = _num(r.get("bpc_market_avg_per_run"), 0.0)
    med = _num(r.get("bpc_market_median_per_run"), 0.0)
    surplus = _num(r.get("bpc_intrinsic_value_surplus"), 0.0)
    return (
        f"<b>蓝图挂牌价差（不是可兑现利润）：</b>当前 {fmt_isk(current)}/流程 · "
        f"同类平均 {fmt_isk(avg)}/流程 · 中位 {fmt_isk(med)}/流程 · 样本 {n}<br>"
        f"按同类挂牌价折算价差 {fmt_isk(surplus)}；仅作为蓝图低估信号。<br>"
    )


def bpc_html(i, r):
    cid = int(float(r["contract_id"]))
    name = _short(r.get("blueprint_name") or r.get("blueprints") or r.get("products") or "BPC", 130)
    name = html.escape(name)
    runs = int(_num(r.get("total_bpc_runs"), 0))
    copies = int(_num(r.get("bpc_copy_count"), 0))
    profit = r.get("net_profit")
    roi = r.get("net_roi")

    lines = [
        f"<b>{i}. {name}</b> · 总流程 {runs}" + (f" · {copies}张" if copies else "") + "<br>",
        f"合同价 {fmt_isk(r.get('contract_price',0))}<br>",
        _bpc_market_html(r),
    ]

    try:
        has_mfg = float(profit) == float(profit) and float(roi) == float(roi)
    except Exception:
        has_mfg = False
    if has_mfg:
        lines.extend(
            [
                f"<b>制造后Jita买单即时兑现：</b>毛收入 {fmt_isk(r.get('gross_revenue',0))} · 净利润 {fmt_isk(profit)} · ROI {float(roi)*100:.1f}%<br>",
                f"材料买入 {fmt_isk(r.get('material_cost_jita_depth',0))} · 制造费 {fmt_isk(r.get('manufacturing_job_cost',0))} · 销售税 {fmt_isk(r.get('sales_tax',0))} · 运输 {fmt_isk(r.get('configured_haul_cost',0))}<br>",
                f"Broker 0 · 改价预留 0 · 买盘容量约 {_num(r.get('market_capacity_contracts',0)):.0f} 批 · 最差成交买价 {fmt_isk(r.get('worst_buy_price_used',0))}<br>",
            ]
        )
    else:
        lines.append("制造路径：当前未进入制造利润候选；蓝图挂牌价差信号仍可独立成立。<br>")

    system = _short(r.get("system_name", ""), 45)
    station = _short(r.get("station_name", ""), 70)
    if system or station:
        lines.append(f"位置 {html.escape(system)} / {html.escape(station)}<br>")
    lines.append(f"<url=contract:0//{cid}><b>打开合同</b></url><br><br>")
    return "".join(lines)


def multi_item_html(i, c):
    r = c["row"]
    cid = int(c["contract_id"])
    items = html.escape(_short(r.get("top_value_items") or r.get("items"), 420))
    risk = html.escape(_short(r.get("risk_tier", "风险未知"), 45))
    system = html.escape(_short(r.get("system_name", ""), 45))
    station = html.escape(_short(r.get("station_name", ""), 80))
    profit = _num(r.get("instant_net_profit", r.get("chosen_value_gap", 0)), 0.0)
    roi = _num(r.get("instant_net_roi", r.get("chosen_roi", 0)), 0.0) * 100
    coverage = _num(r.get("buy_unit_coverage"), 0.0) * 100
    stress = _num(r.get("stress_net_profit"), 0.0)
    return (
        f"<b>{i}. 【多件·Jita买单即时兑现】 · {risk}</b><br>"
        f"合同价 {fmt_isk(r.get('contract_price',0))} · <b>净利润 {fmt_isk(profit)}</b> · ROI {roi:.1f}% · {int(_num(r.get('item_type_count',0)))}种物品<br>"
        f"Jita买单毛值 {fmt_isk(r.get('jita_buy_gross',0))} · 税后/运输后可兑现值 {fmt_isk(r.get('chosen_estimated_value',0))}<br>"
        f"买单数量覆盖 {coverage:.1f}% · 压力利润 {fmt_isk(stress)} · SKIN占比 {_num(r.get('skin_value_share',0))*100:.1f}%<br>"
        + (f"主要物品：{items}<br>" if items else "")
        + f"位置 {system} / {station}<br>"
        + f"<url=contract:0//{cid}><b>打开合同</b></url><br><br>"
    )
