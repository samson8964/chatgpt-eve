"""One short source-backed combined V4 market+contract arbitrage review.

Single recorded full scan, one Jita 4-4 bid exit price convention for both
lanes, no live/order-access claims. The existing scanner and evidence files
are left unchanged. Shared by Gmail and in-game mail.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

from v4.contract_review import make_review as contract_review

JITA = 60003760
WORKER = "https://eve-contract-opener.99617224.workers.dev"
MAX_EACH = 5


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


def render(review: dict, *, game: bool = False) -> tuple[str, str]:
    good = (review.get("coverage_gate") ==
            "INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED" and
            review.get("source_input_integrity") == "ALL_PARSED")
    pairs=review.get("market_research_leads") or []
    contracts=review.get("contract_research_leads",review.get("research_leads")) or []
    if not good:
        pairs,contracts=[],[]
    stamp=str(review.get("run_folder") or "")[:13]
    subject=f"【V4捡漏待核】{stamp} 市场{len(pairs)} 合同{len(contracts)}"
    linebreak="<br>" if game else "\n"
    lines=[
        "V4市场+合同合并简报｜全部按吉他海4买单",
        f"市场审核 {review.get('market_proofs_examined','?')} ｜候选 {review.get('market_research_leads_total',0)}",
        f"合同审核 {review.get('contract_proofs_audited','?')} ｜候选 {review.get('contract_research_leads_total',review.get('research_leads_total',0))}",
    ]
    if not good:
        lines.append("数据不完整：本轮不展示候选。")
    else:
        lines.append("【市场】")
        if not pairs:
            lines.append("本轮无符合门槛的市场候选")
        for n,p in enumerate(pairs[:MAX_EACH],1):
            tid=p["type_id"]
            opener=(f"<url=showinfo:{tid}><b>查看物品</b></url>" if game
                    else p.get("market_url",f"{WORKER}/m/{tid}"))
            lines.append(
                f"{n}. Type {tid} ×{p['quantity']}｜{p['source_location']}→吉他4-4"
                f"｜净{yi(p['net_profit_snapshot'])} ROI{p['roi_snapshot']*100:.1f}%"
                f"｜压{yi(p['stress_profit_snapshot'])} {opener}")
        lines.append("【合同】")
        if not contracts:
            lines.append("本轮无符合审核条件的合同候选")
        for n,p in enumerate(contracts[:MAX_EACH],1):
            cid=int(p["contract_id"])
            opener=(f"<url=contract:0//{cid}><b>打开合同</b></url>" if game
                    else f"{WORKER}/c/{cid}")
            lines.append(
                f"{n}. 合同{cid}｜{p.get('source_location','?')}"
                f"｜价{yi(p.get('contract_price'))}"
                f"｜净{yi(p['net_profit_snapshot'])} ROI{p['roi_snapshot']*100:.1f}%"
                f"｜压{yi(p['stress_profit_snapshot'])} {opener}")
    lines.append("以上均为快照候选，尚未实时验证合同/订单/运输；不可直接购买。")
    return subject, linebreak.join(lines)
