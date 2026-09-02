import hashlib
import html
import os
from pathlib import Path

import pandas as pd
import requests

RESULT = Path("results/latest/ranked_opportunities.csv")
WORKER = os.getenv("EVE_MAIL_WORKER_URL", "https://eve-contract-opener.99617224.workers.dev").rstrip("/")
API_KEY = os.getenv("EVE_MAIL_API_KEY", "").strip()
RECIPIENT_ID = os.getenv("EVE_MAIL_RECIPIENT_ID", "").strip()
RECIPIENT_NAME = os.getenv("EVE_MAIL_RECIPIENT_NAME", "MikeChong").strip()
ESI = "https://esi.evetech.net/latest"


def fmt_isk(v):
    try:
        x = float(v)
    except Exception:
        return "-"
    if abs(x) >= 1e9:
        return f"{x/1e9:.2f}B"
    if abs(x) >= 1e6:
        return f"{x/1e6:.1f}M"
    if abs(x) >= 1e3:
        return f"{x/1e3:.0f}K"
    return f"{x:.0f}"


def fmt_num(v, digits=1):
    try:
        return f"{float(v):.{digits}f}"
    except Exception:
        return "-"


def resolve_recipient_id():
    if RECIPIENT_ID:
        return int(RECIPIENT_ID)
    if not RECIPIENT_NAME:
        raise RuntimeError("Missing EVE_MAIL_RECIPIENT_ID / EVE_MAIL_RECIPIENT_NAME")
    resp = requests.post(
        f"{ESI}/universe/ids/?datasource=tranquility&language=en",
        json=[RECIPIENT_NAME],
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    chars = data.get("characters") or []
    exact = [c for c in chars if str(c.get("name", "")).casefold() == RECIPIENT_NAME.casefold()]
    if not exact:
        raise RuntimeError(f"EVE character not found: {RECIPIENT_NAME}")
    cid = int(exact[0]["id"])
    print(f"Resolved recipient {RECIPIENT_NAME} -> {cid}")
    return cid


def main():
    if not API_KEY:
        print("EVE mail disabled: missing EVE_MAIL_API_KEY")
        return
    if not RESULT.exists():
        print(f"EVE mail skipped: missing {RESULT}")
        return

    recipient_id = resolve_recipient_id()
    df = pd.read_csv(RESULT)
    if df.empty:
        print("EVE mail skipped: no opportunities")
        return

    if "recommendation" in df.columns:
        keep = ~df["recommendation"].fillna("").astype(str).str.startswith("D")
        df = df.loc[keep]
    if "market_capacity_contracts" in df.columns:
        cap = pd.to_numeric(df["market_capacity_contracts"], errors="coerce")
        df = df.loc[cap.fillna(1) >= 1]
    df = df.head(5)

    stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")
    subject = f"BPC套利 {stamp} · {len(df)}个机会"
    parts = [f"<b>EVE BPC 制造套利简报</b><br>{stamp}<br><br>"]

    if df.empty:
        parts.append("当前没有通过筛选的高质量机会。")
    else:
        for i, (_, r) in enumerate(df.iterrows(), 1):
            product = html.escape(str(r.get("products", r.get("blueprints", "Unknown"))))
            cid = int(float(r["contract_id"]))
            type_id = r.get("product_type_id")
            roi = float(r.get("net_roi", 0) or 0) * 100
            profit = fmt_isk(r.get("net_profit"))
            cap = fmt_num(r.get("market_capacity_contracts"), 0)
            vol = fmt_num(r.get("avg_daily_volume_30d"), 1)
            cls = html.escape(str(r.get("opportunity_class", "")))
            score = fmt_num(r.get("opportunity_score"), 1)
            parts.append(f"<b>{i}. {product}</b><br>")
            parts.append(f"净利 {profit} · ROI {roi:.1f}% · 买盘容量 {cap}份<br>")
            parts.append(f"30日均量 {vol}/天 · 评分 {score} · {cls}<br>")
            parts.append(f"<url=contract:0//{cid}><b>打开合同</b></url>")
            try:
                tid = int(float(type_id))
                parts.append(f"　<url=showinfo:{tid}>查看成品</url>")
            except Exception:
                pass
            parts.append("<br><br>")

    parts.append("买合同前请再次核对 BPC 流程/ME/TE 与当前 Jita 买盘。")
    body = "".join(parts)
    digest = hashlib.sha256((subject + body + str(recipient_id)).encode("utf-8")).hexdigest()[:32]

    resp = requests.post(
        f"{WORKER}/api/send-mail",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={
            "recipient_id": recipient_id,
            "subject": subject,
            "body": body,
            "idempotency_key": digest,
        },
        timeout=30,
    )
    print(f"EVE mail worker: HTTP {resp.status_code} {resp.text[:500]}")
    resp.raise_for_status()


if __name__ == "__main__":
    main()
