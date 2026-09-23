from __future__ import annotations

import html
import os
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path

import pandas as pd

import send_global_grade_watch as watch

STATE = Path("results/state/mail_global_grade_watch_gmail_seen.csv")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_USER = os.getenv("GMAIL_SMTP_USER", "").strip()
APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
RECIPIENT = os.getenv("GMAIL_TO", "").strip() or SMTP_USER
MAIL_TOP = int(os.getenv("GRADE_WATCH_GMAIL_TOP", "20"))


def load_seen() -> set[str] | None:
    if not STATE.exists():
        return None
    df = watch.read_csv(STATE)
    if df.empty or "opportunity_key" not in df.columns:
        return set()
    return set(df["opportunity_key"].dropna().astype(str).tolist())


def save_seen(seen: set[str]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    now = pd.Timestamp.now(tz="UTC").isoformat()
    pd.DataFrame(
        [{"opportunity_key": key, "recorded_at": now} for key in sorted(seen)],
        columns=["opportunity_key", "recorded_at"],
    ).to_csv(STATE, index=False)


def _money(v) -> str:
    return watch.fmt_isk(v)


def _link(r: dict) -> str:
    if r.get("contract_id"):
        return r.get("eve_contract_url") or f"https://eve-contract-opener.99617224.workers.dev/c/{int(r['contract_id'])}"
    if r.get("eve_market_url"):
        return str(r["eve_market_url"])
    if r.get("type_id"):
        return f"https://eve-contract-opener.99617224.workers.dev/m/{int(r['type_id'])}"
    return ""


def render_html(stamp: str, rows: list[dict]) -> tuple[str, str, str]:
    subject = f"【EVE捡漏】新增A/S级机会 {stamp} · {len(rows)}个"
    plain = [
        f"EVE 全局捡漏：新增 A/S 级机会 {stamp}",
        "",
        "仅包含首次出现的 A/S 高评分机会；存量不补发，已提醒过的不重复。",
        "",
    ]
    cards = [
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:900px;margin:auto;color:#1f2937">',
        f'<h2 style="margin-bottom:6px">EVE 全局捡漏 · 新增 A/S 级机会</h2>',
        f'<div style="color:#6b7280;margin-bottom:18px">{html.escape(stamp)} · 本次 {len(rows)} 个</div>',
        '<div style="padding:10px 14px;background:#f3f4f6;border-radius:8px;margin-bottom:18px">'
        '仅包含首次出现的 A/S 高评分机会；当前存量不补发，已经提醒过的机会以后不重复。'
        '</div>',
    ]

    for i, r in enumerate(rows, 1):
        labels = " + ".join(r.get("source_labels", []))
        title = html.escape(str(r.get("title", ""))[:220])
        grade = html.escape(str(r.get("grade", "")))
        status = html.escape(str(r.get("status", "")))
        score = float(r.get("score", 0) or 0)
        profit = float(r.get("profit", 0) or 0)
        roi = r.get("roi")
        stress = r.get("stress_profit")
        system = html.escape(str(r.get("system_name", ""))[:60])
        station = html.escape(str(r.get("station_name", ""))[:110])
        risk = html.escape(str(r.get("risk_tier", ""))[:50])
        items = html.escape(str(r.get("items", ""))[:600])
        note = html.escape(str(r.get("note", ""))[:260])
        link = _link(r)

        plain.append(f"{i}. {grade}级 / {score:.1f}分 / {status}")
        plain.append(f"来源：{labels}")
        plain.append(title)
        plain.append(f"净利润/价值差：{_money(profit)}" + (f"；ROI：{float(roi)*100:.1f}%" if roi is not None else ""))
        if stress is not None:
            plain.append(f"压力利润：{_money(stress)}")
        if system or station:
            plain.append(f"位置：{system} / {station}")
        if link:
            plain.append(link)
        plain.append("")

        cards.append(
            '<div style="border:1px solid #e5e7eb;border-radius:10px;padding:16px;margin:0 0 14px 0">'
            f'<div style="font-size:18px;font-weight:700;margin-bottom:6px">{i}. {grade}级 · {score:.1f}分 · {status}</div>'
            f'<div style="color:#4b5563;margin-bottom:8px">来源：{html.escape(labels)}</div>'
            f'<div style="font-weight:600;margin-bottom:10px">{title}</div>'
        )
        if r.get("primary_source") == "BPC价值低估":
            cards.append(f'<div>估值价差：<b>{html.escape(_money(profit))}</b>')
        else:
            cards.append(f'<div>净利润/价值差：<b>{html.escape(_money(profit))}</b>')
        if roi is not None:
            cards.append(f' · ROI <b>{float(roi)*100:.1f}%</b>')
        cards.append('</div>')
        if stress is not None:
            cards.append(f'<div>压力情景利润：{html.escape(_money(stress))}</div>')
        if system or station:
            cards.append(f'<div>位置：{system} / {station}' + (f' · {risk}' if risk else '') + '</div>')
        if items:
            cards.append(f'<div style="margin-top:8px;color:#4b5563">主要价值：{items}</div>')
        if note:
            cards.append(f'<div style="margin-top:8px;color:#92400e">{note}</div>')
        if link:
            cards.append(
                f'<div style="margin-top:12px"><a href="{html.escape(link)}" '
                'style="display:inline-block;padding:8px 12px;background:#111827;color:#fff;text-decoration:none;border-radius:6px">'
                '查看机会</a></div>'
            )
        cards.append('</div>')

    cards.append('</div>')
    return subject, "\n".join(plain), "".join(cards)


def send_gmail(subject: str, plain: str, html_body: str) -> None:
    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = RECIPIENT
    msg["Subject"] = subject
    msg.set_content(plain)
    msg.add_alternative(html_body, subtype="html")

    last = None
    for attempt in range(1, 4):
        try:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
                smtp.login(SMTP_USER, APP_PASSWORD)
                smtp.send_message(msg)
            print(f"gmail-grade-watch sent to {RECIPIENT} attempt={attempt}")
            return
        except Exception as exc:
            last = exc
            if attempt >= 3:
                break
            delay = 2 * attempt
            print(f"gmail-grade-watch retry attempt={attempt} error={type(exc).__name__}; sleep={delay}s")
            time.sleep(delay)
    raise RuntimeError(f"Gmail SMTP delivery failed: {type(last).__name__}: {last}")


def main() -> None:
    if not SMTP_USER or not APP_PASSWORD:
        print("gmail-grade-watch disabled: missing GMAIL_SMTP_USER or GMAIL_APP_PASSWORD")
        return

    candidates, readable_sources = watch.collect_candidates()
    if readable_sources < 6:
        raise RuntimeError(f"Gmail grade-watch source set incomplete: readable_sources={readable_sources}")

    current_keys = set(candidates)
    seen = load_seen()

    # Explicit no-stock-mail rule: first configured run creates a Gmail-specific
    # baseline but sends nothing.
    if seen is None:
        save_seen(current_keys)
        print(f"gmail-grade-watch baseline initialized: {len(current_keys)} existing A/S identities; no stock mail")
        return

    new_keys = current_keys - seen
    if not new_keys:
        print("gmail-grade-watch skipped: no first-seen A/S opportunity")
        return

    ordered = sorted(
        (candidates[k] for k in new_keys),
        key=lambda r: (r["score"], r["profit"], r["roi"] or 0.0),
        reverse=True,
    )
    live = watch.live_filter(ordered)
    if not live:
        print("gmail-grade-watch: new A/S identities are no longer live/visible")
        return

    sent_keys: set[str] = set()
    batches = [live[i:i + MAIL_TOP] for i in range(0, len(live), MAIL_TOP)]
    for batch in batches:
        stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")
        subject, plain, html_body = render_html(stamp, batch)
        send_gmail(subject, plain, html_body)
        sent_keys.update(r["opportunity_key"] for r in batch)
        # Persist after every successful batch so a later failure cannot duplicate
        # already-delivered Gmail alerts.
        save_seen(seen | sent_keys)

    print(f"gmail-grade-watch complete: first_seen_sent={len(sent_keys)}")


if __name__ == "__main__":
    main()
