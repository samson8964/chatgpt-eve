import hashlib
import html
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

RESULT = Path("results/latest/ranked_opportunities.csv")
META = Path("results/latest/meta.json")
WORKER = os.getenv("EVE_MAIL_WORKER_URL", "https://eve-contract-opener.99617224.workers.dev").rstrip("/")
API_KEY = os.getenv("EVE_MAIL_API_KEY", "").strip()
RECIPIENT_NAME = os.getenv("EVE_MAIL_RECIPIENT_NAME", "MikeChong").strip()
ESI = "https://esi.evetech.net/latest"
MAIL_MIN_PROFIT = float(os.getenv("MAIL_MIN_NET_PROFIT", "20000000"))
MAIL_MIN_ROI = float(os.getenv("MAIL_MIN_NET_ROI", "0.08"))
MAIL_TOP = int(os.getenv("MAIL_TOP", "10"))
MAIL_LIVE_POOL = int(os.getenv("MAIL_LIVE_POOL", "50"))
LIVE_CHECK_WORKERS = int(os.getenv("LIVE_CHECK_WORKERS", "10"))


def fmt_isk(v):
    x = float(v)
    if abs(x) >= 1e9:
        return f"{x/1e9:.2f}B"
    if abs(x) >= 1e6:
        return f"{x/1e6:.1f}M"
    return f"{x:,.0f}"


def resolve_character(name):
    r = requests.post(f"{ESI}/universe/ids/?datasource=tranquility", json=[name], timeout=30)
    r.raise_for_status()
    chars = r.json().get("characters") or []
    exact = [c for c in chars if str(c.get("name", "")).casefold() == name.casefold()]
    if not exact:
        raise RuntimeError(f"EVE character not found: {name}")
    return int(exact[0]["id"])


def contract_is_live(contract_id):
    """Return True only when ESI still exposes the public contract items.

    ESI returns 204 when a public contract has expired or was recently accepted,
    and 404 when it is no longer available. Retry transient server/rate errors once.
    """
    url = f"{ESI}/contracts/public/items/{int(contract_id)}/"
    for attempt in range(2):
        try:
            r = requests.get(url, params={"datasource": "tranquility", "page": 1}, timeout=20)
        except requests.RequestException:
            if attempt == 0:
                continue
            return False
        if r.status_code == 200:
            return True
        if r.status_code in (204, 403, 404):
            return False
        if r.status_code in (420, 429, 500, 502, 503, 504) and attempt == 0:
            continue
        return False
    return False


def live_filter(df):
    if df.empty:
        return df

    pool = df.head(max(MAIL_TOP, MAIL_LIVE_POOL)).copy()
    live = {}
    with ThreadPoolExecutor(max_workers=min(LIVE_CHECK_WORKERS, len(pool))) as ex:
        futs = {}
        for idx, row in pool.iterrows():
            cid = int(float(row["contract_id"]))
            futs[ex.submit(contract_is_live, cid)] = (idx, cid)
        for fut in as_completed(futs):
            idx, cid = futs[fut]
            try:
                live[idx] = bool(fut.result())
            except Exception:
                live[idx] = False

    mask = pd.Series([live.get(idx, False) for idx in pool.index], index=pool.index)
    removed = int((~mask).sum())
    kept = pool.loc[mask].head(MAIL_TOP).copy()
    print(f"Live contract recheck: pool={len(pool)} removed={removed} kept={len(kept)} target={MAIL_TOP}")
    return kept


def main():
    if not API_KEY:
        raise RuntimeError("Missing EVE_MAIL_API_KEY")
    if not RESULT.exists():
        raise RuntimeError(f"Missing scan result: {RESULT}")

    recipient_id = resolve_character(RECIPIENT_NAME)
    try:
        df = pd.read_csv(RESULT)
    except pd.errors.EmptyDataError:
        df = pd.DataFrame()

    total = len(df)
    strong_total = 0
    if not df.empty:
        profit = pd.to_numeric(df.get("net_profit"), errors="coerce").fillna(0)
        roi = pd.to_numeric(df.get("net_roi"), errors="coerce").fillna(0)
        keep = (profit >= MAIL_MIN_PROFIT) & (roi >= MAIL_MIN_ROI)
        if "market_capacity_contracts" in df.columns:
            cap = pd.to_numeric(df["market_capacity_contracts"], errors="coerce").fillna(0)
            keep &= cap >= 1
        if "recommendation" in df.columns:
            keep &= ~df["recommendation"].fillna("").astype(str).str.startswith("D")
        df = df.loc[keep].sort_values(["opportunity_score", "net_profit"], ascending=[False, False])
        strong_total = len(df)
        df = live_filter(df)

    stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")
    meta = {}
    if META.exists():
        try:
            meta = json.loads(META.read_text("utf-8"))
        except Exception:
            pass

    if df.empty:
        subject = f"BPC扫描完成 {stamp} · 暂无可抢机会"
        body = (
            f"<b>EVE BPC 快速扫描完成</b><br>{stamp}<br><br>"
            f"本轮主榜 {total} 个；强候选 {strong_total} 个，但发送前实时复核后没有仍可用的合同。<br>"
            f"筛选标准：净利≥{fmt_isk(MAIL_MIN_PROFIT)}、ROI≥{MAIL_MIN_ROI*100:.0f}%、买盘容量≥1批。<br><br>"
            "这封状态邮件也表示 GitHub → LadyGuaGua → MikeChong 推送链路正常。"
        )
    else:
        subject = f"BPC捡漏 {stamp} · {len(df)}个现存机会"
        parts = [f"<b>EVE BPC 捡漏简报</b><br>{stamp}<br>"]
        if meta:
            parts.append(f"精算通过 {meta.get('all_executable_count','-')} · 主榜 {meta.get('ranked_count','-')}<br>")
        parts.append(f"强候选 {strong_total} · 发送前已复核合同存活<br><br>")
        for i, (_, r) in enumerate(df.iterrows(), 1):
            product = html.escape(str(r.get("products", "Unknown")))
            cid = int(float(r["contract_id"]))
            roi = float(r.get("net_roi", 0)) * 100
            cap = float(r.get("market_capacity_contracts", 0) or 0)
            avg30 = float(r.get("avg_daily_volume_30d", 0) or 0)
            score = float(r.get("opportunity_score", 0) or 0)
            parts.append(f"<b>{i}. {product}</b><br>")
            parts.append(f"净利 {fmt_isk(r.get('net_profit',0))} · ROI {roi:.1f}% · 容量 {cap:.0f}批<br>")
            parts.append(f"30日均量 {avg30:.1f}/天 · 评分 {score:.1f}<br>")
            parts.append(f"<url=contract:0//{cid}><b>打开合同</b></url>")
            try:
                tid = int(float(r.get("product_type_id")))
                parts.append(f"　<url=showinfo:{tid}>查看成品</url>")
            except Exception:
                pass
            parts.append("<br><br>")
        parts.append("合同在发送前已做 ESI 存活复核；下单前仍请核对 BPC runs/ME/TE 与 Jita 买盘。")
        body = "".join(parts)

    digest = hashlib.sha256((subject + body + str(recipient_id)).encode()).hexdigest()[:32]
    r = requests.post(
        f"{WORKER}/api/send-mail",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"recipient_id": recipient_id, "subject": subject, "body": body, "idempotency_key": digest},
        timeout=30,
    )
    print(f"EVE mail worker: HTTP {r.status_code} {r.text[:500]}")
    r.raise_for_status()


if __name__ == "__main__":
    main()
