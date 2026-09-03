from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

import send_eve_mail_dual as base
from send_eve_mail_fast import resolve_character, contract_is_live

DEALS = Path("results/latest/contract_deals.csv")
BPC = Path("results/latest/ranked_opportunities.csv")
BPC_VALUE = Path("results/latest/bpc_value_opportunities.csv")
HISTORY = Path("results/state/mail_push_history.csv")

MAIL_TOP = int(os.getenv("MAIL_TOP", "10"))
LIVE_POOL = int(os.getenv("MAIL_LIVE_POOL", "80"))
LIVE_WORKERS = int(os.getenv("LIVE_CHECK_WORKERS", "10"))
COOLDOWN_HOURS = float(os.getenv("MAIL_REPEAT_COOLDOWN_HOURS", "24"))
REPEAT_IMPROVEMENT = float(os.getenv("MAIL_REPEAT_IMPROVEMENT", "0.25"))
FRESHNESS_WEIGHT = float(os.getenv("MAIL_FRESHNESS_WEIGHT", "2.0"))


def read_csv(path: Path) -> pd.DataFrame:
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


def truth(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "t", "yes", "y"}


def freshness(r):
    return finite(r.get("mail_freshness_score"), -40.0)


def age_hours(r):
    return finite(r.get("contract_age_hours"), -1.0)


def freshness_label(r):
    h = age_hours(r)
    if h < 0:
        return "发布时间未知"
    if h < 1:
        return f"新合同 · 发布约{max(1, int(h*60))}分钟"
    return f"发布约{h:.1f}小时"


def candidate_metric(channel, row):
    if channel == "spot-deals":
        return max(0.0, finite(row.get("mail_stress_net_profit"), finite(row.get("instant_net_profit"), 0.0)))
    # BPC cooldown/re-push decisions must use executable manufacturing profit only.
    # Comparable contract ASK-price surplus is not realised profit.
    return max(0.0, finite(row.get("net_profit"), 0.0))


def intrinsic_bonus(row):
    """Secondary ranking bonus after manufacturing economics have already passed the mail gate."""
    if not truth(row.get("bpc_intrinsic_signal")):
        return 0.0
    davg = finite(row.get("bpc_discount_vs_avg"), 0.0)
    dmed = finite(row.get("bpc_discount_vs_median"), 0.0)
    surplus = max(0.0, finite(row.get("bpc_intrinsic_value_surplus"), 0.0))
    discount = max(0.0, -min(davg, dmed))
    return min(50.0, discount / 0.60 * 30.0 + surplus / 200_000_000 * 20.0)


def load_history():
    df = read_csv(HISTORY)
    if df.empty:
        return pd.DataFrame(columns=["channel", "contract_id", "sent_at", "metric"])
    for col in ["channel", "contract_id", "sent_at", "metric"]:
        if col not in df.columns:
            df[col] = "" if col in {"channel", "sent_at"} else 0
    df["contract_id"] = pd.to_numeric(df["contract_id"], errors="coerce").fillna(0).astype(int)
    df["metric"] = pd.to_numeric(df["metric"], errors="coerce").fillna(0.0)
    df["sent_at"] = pd.to_datetime(df["sent_at"], utc=True, errors="coerce")
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=30)
    return df[df["sent_at"].isna() | (df["sent_at"] >= cutoff)].copy()


def cooldown_filter(candidates, channel, history):
    now = pd.Timestamp.now(tz="UTC")
    recent = history[history["channel"].astype(str) == channel].copy()
    by_id = {}
    if not recent.empty:
        recent.sort_values("sent_at", inplace=True)
        for _, r in recent.iterrows():
            by_id[int(r["contract_id"])] = r

    kept = []
    cooled = 0
    improved = 0
    for c in candidates:
        cid = int(c["contract_id"])
        old = by_id.get(cid)
        if old is None or pd.isna(old.get("sent_at")):
            kept.append(c)
            continue
        hours = (now - old["sent_at"]).total_seconds() / 3600.0
        if hours >= COOLDOWN_HOURS:
            kept.append(c)
            continue
        old_metric = max(0.0, finite(old.get("metric"), 0.0))
        new_metric = candidate_metric(channel, c["row"])
        threshold = old_metric * (1.0 + REPEAT_IMPROVEMENT)
        if old_metric <= 0 or new_metric >= threshold:
            c = dict(c)
            c["repeat_improved"] = True
            kept.append(c)
            improved += 1
        else:
            cooled += 1
    return kept, cooled, improved


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


def build_spot_candidates():
    df = read_csv(DEALS)
    out = []
    if df.empty:
        return out
    for _, r in df.iterrows():
        if "mail_eligible" in df.columns and not truth(r.get("mail_eligible")):
            continue
        cls = str(r.get("deal_class", ""))
        if not cls.startswith("A"):
            continue
        risk_rank = finite(r.get("risk_rank"), 5.0)
        stress_roi = max(0.0, finite(r.get("mail_stress_net_roi"), 0.0))
        priority = (
            400.0
            + finite(r.get("deal_score"), 0.0)
            + FRESHNESS_WEIGHT * freshness(r)
            + min(40.0, stress_roi / 0.30 * 40.0)
            - risk_rank * 3.0
        )
        out.append({"priority": priority, "contract_id": int(float(r["contract_id"])), "row": r.copy()})
    out.sort(key=lambda x: (x["priority"], candidate_metric("spot-deals", x["row"])), reverse=True)
    return out


def build_bpc_candidates():
    # Only manufacturing-proven rows may reach mail. Intrinsic BPC market value remains
    # attached to ranked_opportunities.csv and can add a secondary bonus, but it cannot
    # independently create an EVE-mail opportunity.
    out = []
    mfg = read_csv(BPC)
    if mfg.empty or "contract_id" not in mfg.columns:
        return out

    for _, r in mfg.iterrows():
        if "mail_eligible" in mfg.columns and not truth(r.get("mail_eligible")):
            continue
        cid = int(float(r["contract_id"]))
        priority = (
            360.0
            + finite(r.get("opportunity_score"), 0.0)
            + FRESHNESS_WEIGHT * freshness(r)
            + intrinsic_bonus(r)
        )
        out.append({
            "priority": priority,
            "contract_id": cid,
            "row": r.copy(),
            "source": "manufacturing+intrinsic" if truth(r.get("bpc_intrinsic_signal")) else "manufacturing",
        })

    out.sort(key=lambda x: (x["priority"], candidate_metric("bpc-value", x["row"])), reverse=True)
    return out


def record_history(history, channel, picked):
    if not picked:
        return history
    now = pd.Timestamp.now(tz="UTC").isoformat()
    rows = []
    for c in picked:
        rows.append({
            "channel": channel,
            "contract_id": int(c["contract_id"]),
            "sent_at": now,
            "metric": candidate_metric(channel, c["row"]),
        })
    add = pd.DataFrame(rows)
    out = pd.concat([history, add], ignore_index=True)
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(HISTORY, index=False)
    return out


def send_spot(recipient_id, stamp, history):
    raw = build_spot_candidates()
    candidates, cooled, improved = cooldown_filter(raw, "spot-deals", history)
    picked, removed = live_pick(candidates)

    if not picked:
        subject = f"现货捡漏 {stamp} · 暂无新的强机会"
        body = (
            f"<b>现货即时兑现捡漏</b><br>{stamp}<br><br>"
            f"严格候选 {len(raw)} 个；24小时重复冷却 {cooled} 个；发送前失效/不可见 {removed} 个。<br>"
            "邮件只推A类即时买单机会，并要求Jita买价整体下跌5%后仍满足利润/ROI门槛；B类挂单机会只保留在CSV观察榜。"
        )
    else:
        subject = f"现货捡漏 {stamp} · {len(picked)}个新机会"
        parts = [
            f"<b>现货即时兑现捡漏 TOP{len(picked)}</b><br>{stamp}<br>",
            f"严格候选 {len(raw)} · 重复冷却 {cooled} · 改善后允许重推 {improved} · 失效/不可见 {removed}<br>",
            "排序大幅偏重新合同；只推A类即时买单，并通过5%不利价格压力测试。<br><br>",
        ]
        for i, c in enumerate(picked, 1):
            parts.append(f"<b>{freshness_label(c['row'])}</b><br>")
            parts.append(base.deal_html(i, c["row"]))
        parts.append("说明：新合同优先不是放宽利润门槛；新鲜度只在已经通过严格可兑现性筛选的机会之间决定优先级。")
        body = "".join(parts)

    base.send_mail(recipient_id, subject, body, "spot-deals")
    return record_history(history, "spot-deals", picked)


def send_bpc(recipient_id, stamp, history):
    raw = build_bpc_candidates()
    candidates, cooled, improved = cooldown_filter(raw, "bpc-value", history)
    picked, removed = live_pick(candidates)

    if not picked:
        subject = f"BPC捡漏 {stamp} · 暂无新的可执行机会"
        body = (
            f"<b>BPC蓝图捡漏</b><br>{stamp}<br><br>"
            f"制造利润严格候选 {len(raw)} 个；24小时重复冷却 {cooled} 个；发送前失效/不可见 {removed} 个。<br>"
            "同类BPC挂牌均价/中位价现在只作辅助估值和排序，不能单独构成推送理由；必须先通过制造净利润、净ROI和买盘容量门槛。"
        )
    else:
        subject = f"BPC捡漏 {stamp} · {len(picked)}个新机会"
        parts = [
            f"<b>BPC蓝图可执行捡漏 TOP{len(picked)}</b><br>{stamp}<br>",
            f"制造利润严格候选 {len(raw)} · 重复冷却 {cooled} · 改善后允许重推 {improved} · 失效/不可见 {removed}<br>",
            "先要求制造后全成本利润可执行；BPC自身每流程折价只作为额外价值和排序加分。新合同优先。<br><br>",
        ]
        for i, c in enumerate(picked, 1):
            parts.append(f"<b>{freshness_label(c['row'])}</b><br>")
            parts.append(base.bpc_html(i, c["row"]))
        parts.append("说明：其他公开合同的挂牌价不等于真实成交价，因此蓝图自身估值不再被当作独立利润。")
        body = "".join(parts)

    base.send_mail(recipient_id, subject, body, "bpc-value")
    return record_history(history, "bpc-value", picked)


def main():
    if not base.API_KEY:
        raise RuntimeError("Missing EVE_MAIL_API_KEY")
    recipient_id = resolve_character(base.RECIPIENT_NAME)
    stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")
    history = load_history()
    history = send_spot(recipient_id, stamp, history)
    send_bpc(recipient_id, stamp, history)


if __name__ == "__main__":
    main()
