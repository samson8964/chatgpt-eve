from __future__ import annotations

import html
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

import send_eve_mail_dual as base
from send_eve_mail_fast import resolve_character, contract_is_live, fmt_isk

SOURCE = Path("results/latest/multi_item_contract_deals.csv")
STATE = Path("results/state/mail_last_multi_top10.csv")
MAIL_TOP = int(os.getenv("MAIL_TOP", "10"))
LIVE_POOL = int(os.getenv("MAIL_LIVE_POOL", "80"))
LIVE_WORKERS = int(os.getenv("LIVE_CHECK_WORKERS", "10"))


def read_csv(path: Path):
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def finite(v, default=0.0):
    try:
        x = float(v)
        return x if pd.notna(x) and x not in (float("inf"), float("-inf")) else default
    except Exception:
        return default


def short(v, n=170):
    s = " ".join(str(v or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def live_pick(candidates):
    pool = candidates[: max(MAIL_TOP, LIVE_POOL)]
    if not pool:
        return [], 0
    states = {}
    with ThreadPoolExecutor(max_workers=min(LIVE_WORKERS, len(pool))) as ex:
        futs = {ex.submit(contract_is_live, int(c["contract_id"])): i for i, c in enumerate(pool)}
        for fut in as_completed(futs):
            i = futs[fut]
            try:
                states[i] = bool(fut.result())
            except Exception:
                states[i] = False
    live = [c for i, c in enumerate(pool) if states.get(i, False)]
    return live[:MAIL_TOP], len(pool) - len(live)


def load_last_signature():
    df = read_csv(STATE)
    if df.empty or "contract_id" not in df.columns:
        return []
    if "rank" in df.columns:
        df = df.sort_values("rank")
    return [int(x) for x in pd.to_numeric(df["contract_id"], errors="coerce").dropna().astype(int).tolist()]


def save_signature(picked):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"rank": i, "contract_id": int(c["contract_id"])} for i, c in enumerate(picked, 1)]
    pd.DataFrame(rows, columns=["rank", "contract_id"]).to_csv(STATE, index=False)


def build_candidates():
    df = read_csv(SOURCE)
    if df.empty:
        return []
    out = []
    for _, r in df.iterrows():
        try:
            cid = int(float(r["contract_id"]))
        except Exception:
            continue
        gap = finite(r.get("chosen_value_gap"), 0.0)
        roi = finite(r.get("chosen_roi"), 0.0)
        out.append({"contract_id": cid, "gap": gap, "roi": roi, "row": r.copy()})
    out.sort(key=lambda x: (x["gap"], x["roi"]), reverse=True)
    return out


def item_html(i, c):
    r = c["row"]
    cid = int(c["contract_id"])
    cls = str(r.get("deal_class", ""))
    tag = "【多件-A 即时】" if cls.startswith("A") else "【多件-B 价值低估】"
    price = finite(r.get("contract_price"), 0.0)
    value = finite(r.get("chosen_estimated_value"), 0.0)
    gap = finite(r.get("chosen_value_gap"), 0.0)
    discount = finite(r.get("chosen_discount"), 0.0) * 100
    roi = finite(r.get("chosen_roi"), 0.0) * 100
    coverage = finite(r.get("value_coverage"), 0.0) * 100
    buy_cov = finite(r.get("buy_unit_coverage"), 0.0) * 100
    top1 = finite(r.get("top1_value_share"), 0.0) * 100
    top3 = finite(r.get("top3_value_share"), 0.0) * 100
    types = int(finite(r.get("item_type_count"), 0.0))
    sec = finite(r.get("security"), 0.0)
    jumps = int(finite(r.get("shortest_jumps_to_jita"), -1.0))
    risk = html.escape(short(r.get("risk_tier", "风险未知"), 42))
    system = html.escape(short(r.get("system_name", ""), 45))
    station = html.escape(short(r.get("station_name", ""), 72))
    items = html.escape(short(r.get("top_value_items", ""), 420))

    if cls.startswith("A"):
        valuation_line = (
            f"Jita即时买单毛值 {fmt_isk(r.get('jita_buy_gross',0))} · "
            f"立即兑现净值 {fmt_isk(r.get('instant_liquidation_net_value',0))} · 买单覆盖 {buy_cov:.0f}%"
        )
        caveat = "A类按当前真实买单深度估算，适合判断买回后立即兑现。"
    else:
        valuation_line = (
            f"Jita卖单原始估值 {fmt_isk(r.get('jita_sell_gross_raw',0))} · "
            f"流动性折扣后毛值 {fmt_isk(r.get('liquidity_adjusted_market_gross',0))} · "
            f"扣交易费用后净值 {fmt_isk(r.get('market_net_value',0))}"
        )
        caveat = "B类是流动性折扣后的正常挂卖价值，不代表立即可兑现。"

    concentration = f"最大单品占 {top1:.0f}% · TOP3占 {top3:.0f}%"
    if top1 >= 70:
        concentration += " · <b>价值高度集中</b>"

    return (
        f"<b>{i}. {tag} · {risk}</b><br>"
        f"合同价 {fmt_isk(price)} · 估值 {fmt_isk(value)} · 价值差 {fmt_isk(gap)}<br>"
        f"相对估值折价 {discount:.1f}% · 潜在ROI {roi:.1f}% · {types}种物品 · 估值覆盖 {coverage:.0f}%<br>"
        f"{valuation_line}<br>"
        f"交易成本：物流预留 {fmt_isk(r.get('haul_reserve',0))} · 体积约 {finite(r.get('total_m3'),0):,.0f} m³<br>"
        f"{concentration}<br>"
        + (f"主要物品：{items}<br>" if items else "")
        + f"位置 {system} / {station} · 安全等级 {sec:.1f} · Jita最短 {jumps}跳<br>"
        f"{caveat}<br>"
        f"<url=contract:0//{cid}><b>打开合同</b></url><br><br>"
    )


def main():
    if not base.API_KEY:
        raise RuntimeError("Missing EVE_MAIL_API_KEY")

    recipient_id = resolve_character(base.RECIPIENT_NAME)
    candidates = build_candidates()
    picked, removed = live_pick(candidates)
    signature = [int(c["contract_id"]) for c in picked]
    previous = load_last_signature()

    if signature == previous:
        print(f"multi-item mail skipped: unchanged TOP{len(signature)}")
        return

    stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")
    if not picked:
        subject = f"多件合同捡漏 {stamp} · 暂无强机会"
        body = (
            f"<b>多件物品合同捡漏</b><br>{stamp}<br><br>"
            f"当前无满足条件且仍有效的合同；发送前失效/不可见 {removed} 个。<br>"
            "门槛：至少2种物品、地点可达、估值覆盖≥90%、相对估值折价≥30%、绝对价值差≥30M。"
        )
    else:
        subject = f"多件合同捡漏 {stamp} · TOP{len(picked)}"
        parts = [
            f"<b>多件物品合同捡漏 TOP{len(picked)}</b><br>{stamp}<br>",
            f"强候选 {len(candidates)} · 发送前失效/不可见 {removed}<br>",
            "A=当前Jita买单深度下可立即兑现；B=流动性折扣后的正常市场价值。统一要求地点可达、估值覆盖≥90%、折价≥30%、价值差≥30M。<br>",
            "排序只看绝对净价值差；如果TOP10合同及顺序完全不变，本频道不会重复发邮件。<br><br>",
        ]
        for i, c in enumerate(picked, 1):
            parts.append(item_html(i, c))
        body = "".join(parts)

    base.send_mail(recipient_id, subject, body, "multi-item-deals")
    save_signature(picked)


if __name__ == "__main__":
    main()
