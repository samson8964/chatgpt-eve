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


def candidate_metric(channel, row):
    if channel == "spot-deals":
        return max(0.0, finite(row.get("mail_net_profit"), 0.0))
    return max(
        0.0,
        finite(row.get("bpc_intrinsic_value_surplus"), 0.0) if truth(row.get("bpc_intrinsic_signal")) else 0.0,
        finite(row.get("net_profit"), 0.0) if truth(row.get("bpc_manufacturing_signal")) else 0.0,
        finite(row.get("mail_value_gap_isk"), 0.0),
    )


def load_history():
    """Keep one compact row per contract/channel and migrate the old event log automatically."""
    df = read_csv(HISTORY)
    columns = ["channel", "contract_id", "last_sent_at", "metric", "push_count"]
    if df.empty:
        return pd.DataFrame(columns=columns)

    for col in ["channel", "contract_id", "metric"]:
        if col not in df.columns:
            df[col] = "" if col == "channel" else 0
    df["contract_id"] = pd.to_numeric(df["contract_id"], errors="coerce").fillna(0).astype(int)
    df["metric"] = pd.to_numeric(df["metric"], errors="coerce").fillna(0.0)

    # New compact format.
    if "last_sent_at" in df.columns and "push_count" in df.columns:
        df["last_sent_at"] = pd.to_datetime(df["last_sent_at"], utc=True, errors="coerce")
        df["push_count"] = pd.to_numeric(df["push_count"], errors="coerce").fillna(0).astype(int)
        return df[columns].copy()

    # Old format: one row per send with sent_at. Collapse it while preserving total counts.
    if "sent_at" not in df.columns:
        df["sent_at"] = pd.NaT
    df["sent_at"] = pd.to_datetime(df["sent_at"], utc=True, errors="coerce")
    rows = []
    for (channel, cid), g in df.groupby(["channel", "contract_id"], dropna=False):
        g = g.sort_values("sent_at")
        latest = g.iloc[-1]
        rows.append({
            "channel": str(channel),
            "contract_id": int(cid),
            "last_sent_at": latest.get("sent_at"),
            "metric": finite(latest.get("metric"), 0.0),
            "push_count": int(len(g)),
        })
    return pd.DataFrame(rows, columns=columns)


def get_push_count(history, channel, contract_id):
    if history.empty:
        return 0
    mask = (history["channel"].astype(str) == channel) & (history["contract_id"].astype(int) == int(contract_id))
    if not mask.any():
        return 0
    return int(pd.to_numeric(history.loc[mask, "push_count"], errors="coerce").fillna(0).max())


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
        if not (cls.startswith("A") or cls.startswith("B")):
            continue
        gap = candidate_metric("spot-deals", r)
        roi = max(0.0, finite(r.get("mail_net_roi"), 0.0))
        out.append({
            "priority": gap,
            "roi": roi,
            "contract_id": int(float(r["contract_id"])),
            "row": r.copy(),
        })
    # No freshness bonus and no risk-class bonus: rank by absolute value gap first.
    out.sort(key=lambda x: (x["priority"], x["roi"]), reverse=True)
    return out


def merge_rows(primary, secondary):
    out = primary.copy()
    for k, v in secondary.items():
        cur = out.get(k)
        empty = cur is None or cur == "" or (isinstance(cur, float) and pd.isna(cur))
        if empty:
            out[k] = v
    return out


def build_bpc_candidates():
    """Union intrinsic-value and manufacturing routes; either may independently qualify."""
    best = {}

    for path in [BPC_VALUE, BPC]:
        df = read_csv(path)
        if df.empty or "contract_id" not in df.columns:
            continue
        for _, r in df.iterrows():
            if "mail_eligible" in df.columns and not truth(r.get("mail_eligible")):
                continue
            try:
                cid = int(float(r["contract_id"]))
            except Exception:
                continue
            if cid in best:
                merged = merge_rows(best[cid]["row"].to_dict(), r.to_dict())
                best[cid]["row"] = pd.Series(merged)
            else:
                best[cid] = {"contract_id": cid, "row": r.copy()}

    out = []
    for cid, c in best.items():
        r = c["row"]
        intrinsic = truth(r.get("bpc_intrinsic_signal"))
        manufacturing = truth(r.get("bpc_manufacturing_signal"))
        if intrinsic and manufacturing:
            source = "intrinsic+manufacturing"
        elif intrinsic:
            source = "intrinsic"
        else:
            source = "manufacturing"
        gap = candidate_metric("bpc-value", r)
        roi = max(0.0, finite(r.get("net_roi"), 0.0))
        out.append({
            "priority": gap,
            "roi": roi,
            "contract_id": cid,
            "row": r,
            "source": source,
        })

    # All BPC opportunities also rank by the largest current ISK value gap, not freshness.
    out.sort(key=lambda x: (x["priority"], x["roi"]), reverse=True)
    return out


def record_history(history, channel, picked):
    if not picked:
        HISTORY.parent.mkdir(parents=True, exist_ok=True)
        history.to_csv(HISTORY, index=False)
        return history

    now = pd.Timestamp.now(tz="UTC")
    history = history.copy()
    for c in picked:
        cid = int(c["contract_id"])
        mask = (history["channel"].astype(str) == channel) & (history["contract_id"].astype(int) == cid)
        if mask.any():
            idx = history.index[mask][0]
            history.at[idx, "last_sent_at"] = now
            history.at[idx, "metric"] = candidate_metric(channel, c["row"])
            history.at[idx, "push_count"] = int(finite(history.at[idx, "push_count"], 0)) + 1
        else:
            history.loc[len(history)] = {
                "channel": channel,
                "contract_id": cid,
                "last_sent_at": now,
                "metric": candidate_metric(channel, c["row"]),
                "push_count": 1,
            }

    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    history.to_csv(HISTORY, index=False)
    return history


def spot_tag(row):
    cls = str(row.get("deal_class", ""))
    return "【现货-A 即时】" if cls.startswith("A") else "【现货-B 挂单】"


def bpc_tag(source):
    if source == "intrinsic+manufacturing":
        return "【蓝图-价值+制造】"
    if source == "intrinsic":
        return "【蓝图-价值】"
    return "【蓝图-制造】"


def send_spot(recipient_id, stamp, history):
    candidates = build_spot_candidates()
    picked, removed = live_pick(candidates)

    if not picked:
        subject = f"现货捡漏 {stamp} · 暂无强机会"
        body = (
            f"<b>现货合同捡漏</b><br>{stamp}<br><br>"
            f"合格候选 {len(candidates)} 个；发送前失效/不可见 {removed} 个。<br>"
            "A类即时买单和B类挂单机会均可推送；统一要求净利润≥30M、ROI≥10%。不再做Jita买价下调5%压力测试，也不要求买盘覆盖≥95%。"
        )
    else:
        subject = f"现货捡漏 {stamp} · TOP{len(picked)}"
        parts = [
            f"<b>现货合同捡漏 TOP{len(picked)}</b><br>{stamp}<br>",
            f"合格候选 {len(candidates)} · 失效/不可见 {removed}<br>",
            "排序：只按当前价差空间（净利润ISK）从大到小；A即时买单、B挂单都参与。<br><br>",
        ]
        for i, c in enumerate(picked, 1):
            count = get_push_count(history, "spot-deals", c["contract_id"]) + 1
            parts.append(f"<b>{spot_tag(c['row'])} · 已推送次数：{count}</b><br>")
            parts.append(base.deal_html(i, c["row"]))
        parts.append("说明：B类是挂单潜在利润，不是即时可兑现利润；风险标签继续保留，但不参与价差排名。")
        body = "".join(parts)

    base.send_mail(recipient_id, subject, body, "spot-deals")
    return record_history(history, "spot-deals", picked)


def send_bpc(recipient_id, stamp, history):
    candidates = build_bpc_candidates()
    picked, removed = live_pick(candidates)

    if not picked:
        subject = f"BPC捡漏 {stamp} · 暂无强机会"
        body = (
            f"<b>BPC蓝图捡漏</b><br>{stamp}<br><br>"
            f"合格候选 {len(candidates)} 个；发送前失效/不可见 {removed} 个。<br>"
            "蓝图自身明显低估和制造套利是两条独立入选路径；不再要求必须先通过manufacturing_ok。"
        )
    else:
        subject = f"BPC捡漏 {stamp} · TOP{len(picked)}"
        parts = [
            f"<b>BPC蓝图捡漏 TOP{len(picked)}</b><br>{stamp}<br>",
            f"合格候选 {len(candidates)} · 失效/不可见 {removed}<br>",
            "排序：按蓝图自身低估价值差与制造净利润中的较大价差空间排序，不使用新鲜度加权。<br><br>",
        ]
        for i, c in enumerate(picked, 1):
            count = get_push_count(history, "bpc-value", c["contract_id"]) + 1
            parts.append(f"<b>{bpc_tag(c['source'])} · 已推送次数：{count}</b><br>")
            parts.append(base.bpc_html(i, c["row"]))
        parts.append("说明：蓝图挂牌可比价不是实际成交价，所以价值型机会仍要求样本数、平均/中位折价和绝对价值差同时过线；制造收益只是另一条独立证据。")
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
