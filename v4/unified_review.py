"""One short source-backed combined V4 market+contract arbitrage review.

Single recorded full scan, one Jita 4-4 bid exit price convention for both
lanes, no live/order-access claims. The existing scanner and evidence files
are left unchanged. Shared by Gmail and in-game mail.
"""
from __future__ import annotations

import json
import math
import html
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from v4.contract_review import make_review as contract_review

JITA = 60003760
WORKER = "https://eve-contract-opener.99617224.workers.dev"
MAX_EACH = 5
LOCATION_NAMES = {
    60003760:"吉他4-4", 60008494:"Amarr", 60011866:"Dodixie",
    1053970513596:"4-H", 1049588174021:"C-J",
    1040804972352:"O4T",
}


def place(value) -> str:
    try:
        n = int(value)
    except (ValueError, TypeError, OverflowError):
        return "位置未知"
    return LOCATION_NAMES.get(n, str(n))


def beijing_scan_time(run_name) -> str:
    try:
        value = datetime.strptime(str(run_name)[:16], "%Y%m%dT%H%M%SZ")
        value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone(timedelta(hours=8))).strftime("%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(run_name or "")[:13]


def _amount(value):
    try:
        val = float(value)
        return val if math.isfinite(val) else None
    except (ValueError, TypeError, OverflowError):
        return None


def yi(value) -> str:
    """ISK expressed in 100 million units with 0.01-yi precision."""
    n = _amount(value)
    return f"{n / 100_000_000:.2f}亿" if n is not None else "未知"


def make_review(root: Path, *, limit_each: int = MAX_EACH) -> dict:
    root = Path(root)
    review = contract_review(root, limit=max(MAX_EACH,limit_each))
    folder = root / "runs" / review["run_folder"]
    report = json.loads((folder / "deep_shadow.json").read_text(encoding="utf-8"))
    if report.get("status") != "SHADOW_ONLY_NO_LIVE_ALERTS":
        raise RuntimeError("UNIFIED_REVIEW_REQUIRES_SHADOW_REPORT")
    if report.get("market_pricing_basis") != "JITA_4_4_BUY_DEPTH_SNAPSHOT":
        raise RuntimeError("UNIFIED_REVIEW_REQUIRES_FRESH_JITA_MARKET_SCAN")
    if review.get("contract_pricing_basis") != "JITA_4_4_BUY_DEPTH_SNAPSHOT":
        raise RuntimeError("UNIFIED_REVIEW_REQUIRES_FRESH_JITA_CONTRACT_SCAN")
    rejected = Counter()
    market = []
    examined = 0
    with (folder / "all_proofs.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("kind") != "market":
                continue
            examined += 1
            rejected[str(row.get("reason") or "UNSPECIFIED")] += 1
            if row.get("status") == "MAIL":
                raise RuntimeError("UNVERIFIED_FORMAL_MARKET_MAIL_FORBIDDEN")
            if (row.get("valuation_location_id") != JITA or
                    row.get("valuation_basis") != "JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE" or
                    row.get("destination_location") != JITA or
                    row.get("model_candidate") is not True):
                continue
            source,typ,quantity = row.get("source_location"),row.get("type_id"),row.get("quantity")
            try:
                source,typ,quantity=int(source),int(typ),int(quantity)
            except (ValueError,TypeError,OverflowError):
                continue
            if source <= 0 or typ <= 0 or quantity <= 0 or source == JITA:
                continue
            profit,roi,stress,capital = (_amount(row.get(k)) for k in
                                          ("profit","roi","stress_profit","cost"))
            if (profit is None or roi is None or stress is None or capital is None or
                    profit <= 0 or roi <= 0 or stress <= 0 or capital <= 0):
                continue
            market.append({
                "type_id":typ,"quantity":quantity,
                "source_location":source, "destination_location":JITA,
                "net_profit_snapshot":profit,"roi_snapshot":roi,
                "stress_profit_snapshot":stress,
                "capital":capital,"haul_estimate":_amount(row.get("haul_isk")),
                "market_url":f"{WORKER}/m/{typ}",
                "live_verified":False,"actionable":False,
            })
    expected=int(report.get("market_proofs_examined",-1))
    if examined != expected:
        raise RuntimeError("MARKET_PROOF_COUNT_MISMATCH")
    market.sort(key=lambda row:(-row["net_profit_snapshot"],-row["roi_snapshot"],
                                row["source_location"],row["type_id"]))
    review.update({
        "report_type":"V4_UNIFIED_MARKET_AND_CONTRACT_REVIEW_ONLY",
        "market_pricing_basis":report["market_pricing_basis"],
        "market_potential_pairs":int(report.get("market_potential_pairs") or 0),
        "market_proofs_examined":examined,
        "market_rejection_reasons":dict(rejected.most_common(8)),
        "market_research_leads_total":len(market),
        "market_research_leads":market[:max(0,min(limit_each,12))],
        "contract_research_leads_total":review.get("research_leads_total",0),
        "contract_research_leads":review.get("research_leads",[])[:max(0,min(limit_each,12))],
    })
    return review


def _selected(review: dict):
    good = (review.get("coverage_gate") ==
            "INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED" and
            review.get("source_input_integrity") == "ALL_PARSED")
    if not good:
        return [], [], False
    pairs = (review.get("market_research_leads") or [])[:MAX_EACH]
    contracts = (review.get("contract_research_leads",
                            review.get("research_leads")) or [])[:MAX_EACH]
    return pairs, contracts, True


def _subject(review: dict, pairs: list, contracts: list) -> str:
    time = beijing_scan_time(review.get("run_folder"))
    return f"V4捡漏待核 {time} 市场{len(pairs)} 合同{len(contracts)}"


def render(review: dict, *, game: bool = False) -> tuple[str, str]:
    """Short human-readable body. Game version contains native EVE click targets.

    Important: showinfo opens the item's information, not a particular sell
    order. Contract links open the exact contract identifier in-game.
    """
    pairs, contracts, good = _selected(review)
    subject = _subject(review, pairs, contracts)
    lines = []
    if not good:
        return subject, "本轮数据不完整，未推送机会。"
    if pairs:
        lines.append("【市场】")
        for n, p in enumerate(pairs, 1):
            tid = int(p["type_id"])
            if game:
                name = f"<url=showinfo:{tid}><b>查看商品 {tid}</b></url>"
            else:
                name = f"商品 {tid} {WORKER}/m/{tid}"
            lines.append(
                f"{n}. {name} ×{p['quantity']} {place(p['source_location'])}"
                f" 净{yi(p['net_profit_snapshot'])} ROI{p['roi_snapshot']*100:.0f}%")
    if contracts:
        lines.append("【合同】")
        for n, p in enumerate(contracts, 1):
            cid = int(p["contract_id"])
            if game:
                name = f"<url=contract:0//{cid}><b>打开合同 {cid}</b></url>"
            else:
                name = f"合同 {cid} {WORKER}/c/{cid}"
            lines.append(
                f"{n}. {name} {place(p.get('source_location'))}"
                f" 价{yi(p.get('contract_price'))}"
                f" 净{yi(p['net_profit_snapshot'])} ROI{p['roi_snapshot']*100:.0f}%")
    if not pairs and not contracts:
        lines.append("本轮暂无候选。")
    lines.append("快照待核，不代表可立即成交。")
    # EVE ESI supports <br>, and actual native in-client <url=...> syntax.
    return subject, ("<br>" if game else "\n").join(lines)


def render_html(review: dict) -> tuple[str, str]:
    """HTML Gmail alternative with real anchors, not plain URL text.

    No remote images, scripts, or unsanitized data from contracts; hrefs
    are created only from validated numeric IDs on our own opener domain.
    """
    pairs, contracts, good = _selected(review)
    subject = _subject(review, pairs, contracts)
    blocks = []
    if not good:
        blocks.append("<p>本轮数据不完整，未推送机会。</p>")
    else:
        if pairs:
            blocks.append("<p><strong>市场</strong></p>")
            for n, p in enumerate(pairs, 1):
                tid = int(p["type_id"])
                place_name = html.escape(place(p.get("source_location")))
                blocks.append(
                    f'<p>{n}. <a href="{WORKER}/m/{tid}">查看商品 {tid}</a>'
                    f' ×{int(p["quantity"])} {place_name}'
                    f' ｜净{yi(p["net_profit_snapshot"])}'
                    f' ｜ROI {float(p["roi_snapshot"])*100:.0f}%</p>')
        if contracts:
            blocks.append("<p><strong>合同</strong></p>")
            for n, p in enumerate(contracts, 1):
                cid = int(p["contract_id"])
                place_name = html.escape(place(p.get("source_location")))
                blocks.append(
                    f'<p>{n}. <a href="{WORKER}/c/{cid}">打开合同 {cid}</a>'
                    f' {place_name} ｜价{yi(p.get("contract_price"))}'
                    f' ｜净{yi(p["net_profit_snapshot"])}'
                    f' ｜ROI {float(p["roi_snapshot"])*100:.0f}%</p>')
        if not pairs and not contracts:
            blocks.append("<p>本轮暂无候选。</p>")
    blocks.append('<p style="color:#777;font-size:12px">快照待核，不代表可立即成交。</p>')
    body = ('<!doctype html><html><head><meta charset="utf-8"></head>'
            '<body style="font-family:Arial,sans-serif;font-size:14px;'
            'line-height:1.4">' + "".join(blocks) + '</body></html>')
    return subject, body
