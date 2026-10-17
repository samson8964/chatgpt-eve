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
from v4.engine import Policy
from v4.ship_alert_exclusions import load_policy_for_run, POLICY_NAME
from v4.mail_volume import market_volume, market_label, contract_label, credited_volume_breakdown
from v4.discovery_history import first_seen, order_by_discovery

JITA = 60003760
WORKER = "https://eve-contract-opener.99617224.workers.dev"
MAX_EACH = 10
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


def contract_place(lead: dict) -> str:
    """Identify high/low NPC contract pickup without claiming safe transport."""
    source = place(lead.get("source_location"))
    if source in ("吉他4-4", "Amarr", "Dodixie", "4-H", "C-J", "O4T"):
        return source
    name = lead.get("source_station_name")
    band = lead.get("source_security_band")
    prefix = {"HIGH": "高安NPC", "LOW": "低安NPC"}.get(band, "")
    if isinstance(name, str) and name.strip():
        safe = "".join(ch for ch in name if ch not in "<>&" and ord(ch) >= 32)
        return (prefix + " " if prefix else "") + safe[:95]
    return (prefix + "空间站 " if prefix else "") + source


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



def unit_price(value) -> str:
    """Avoid displaying low per-item prices misleadingly as 0.00亿."""
    amount = _amount(value)
    if amount is None:
        return "无报价"
    if amount >= 1_000_000:
        return f"{amount/100_000_000:.2f}亿"
    if amount >= 10_000:
        return f"{amount/10_000:.2f}万"
    return f"{amount:,.2f}ISK"


def five_level_label(proof: dict, key: str, name: str) -> str:
    depth = proof.get(key)
    if not isinstance(depth, dict) or not (1 <= int(depth.get("group_count") or 0) <= 5):
        return name + "无数据"
    return (name + str(depth["group_count"]) + "档均" +
            unit_price(depth.get("simple_mean_isk_per_unit")))

def make_review(root: Path, *, limit_each: int = MAX_EACH) -> dict:
    root = Path(root)
    # Collect all eligible contracts; truncate only AFTER first-seen ordering.
    review = contract_review(root, limit=None)
    folder = root / "runs" / review["run_folder"]
    report = json.loads((folder / "deep_shadow.json").read_text(encoding="utf-8"))
    if report.get("status") != "SHADOW_ONLY_NO_LIVE_ALERTS":
        raise RuntimeError("UNIFIED_REVIEW_REQUIRES_SHADOW_REPORT")
    if report.get("market_pricing_basis") != "JITA_4_4_BUY_DEPTH_SNAPSHOT":
        raise RuntimeError("UNIFIED_REVIEW_REQUIRES_FRESH_JITA_MARKET_SCAN")
    if report.get("market_execution_basis") != "OPTIMIZED_MATCHED_QUANTITY_AND_VWAP":
        raise RuntimeError("UNIFIED_REVIEW_REQUIRES_DEPTH_VWAP_MARKET_SCAN")
    if review.get("contract_pricing_basis") != "JITA_4_4_BUY_DEPTH_SNAPSHOT":
        raise RuntimeError("UNIFIED_REVIEW_REQUIRES_FRESH_JITA_CONTRACT_SCAN")
    exclusion=load_policy_for_run(report)
    blocked=Counter()
    rejected = Counter()
    market = []
    blueprints = []
    blueprint_examined=0
    examined = 0
    with (folder / "all_proofs.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("kind") == "blueprint_manufacturing":
                blueprint_examined+=1
                # Strictly research-only. Never trust unaudited profit fields
                # that bypass the manufacturing model provenance.
                if (row.get("model_candidate") is True and
                    row.get("status") == "WATCH" and
                    row.get("valuation_basis") ==
                      "JITA_BUY_FINISHED_GOODS_JITA_SELL_MATERIALS_SNAPSHOT" and
                    row.get("facility_fee_status") ==
                      "20_PERCENT_MATERIAL_COST_RESERVE_NOT_FACILITY_VERIFIED" and
                    row.get("jita_material_ask_depth_verified_in_snapshot") is True and
                    row.get("jita_product_buy_depth_verified_in_snapshot") is True):
                    net=_amount(row.get("net_profit"))
                    roi=_amount(row.get("roi"))
                    if net is not None and net>=50_000_000 and roi is not None and roi>.10:
                        if exclusion is not None and exclusion.blocks_blueprint(
                                row.get("blueprint_type_id"),row.get("product_type_id")):
                            blocked["blueprint_manufacturing"]+=1
                            continue
                        blueprints.append({
                            "contract_id":row.get("contract_id"),
                            "blueprint_type_id":row.get("blueprint_type_id"),
                            "blueprint_kind":row.get("blueprint_kind"),
                            "material_efficiency":row.get("material_efficiency"),
                            "production_runs_assumed":row.get("production_runs_assumed"),
                            "product_type_id":row.get("product_type_id"),
                            "product_units":row.get("product_units"),
                            "contract_price":row.get("contract_price_isk"),
                            "product_gross":row.get("product_gross_isk"),
                            "material_cost":row.get("material_cost_isk"),
                            "fee_reserve":row.get("manufacturing_fee_reserve_isk"),
                            "sales_tax":row.get("sales_tax_isk"),
                            "net_profit_snapshot":net,
                            "roi_snapshot":roi,
                            "source_location":row.get("source_location"),
                            "cost_basis":"20% material cost fee reserve; actual facility taxes unverified",
                            "live_verified":False,
                            "actionable":False,
                        })
                continue
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
            if exclusion is not None and exclusion.blocks_market(typ):
                blocked["market"]+=1
                continue
            profit,roi,stress,capital = (_amount(row.get(k)) for k in
                                          ("profit","roi","stress_profit","cost"))
            source_vwap = _amount(row.get("source_vwap_isk_per_unit"))
            jita_vwap = _amount(row.get("jita_vwap_isk_per_unit"))
            if (profit is None or roi is None or stress is None or capital is None or
                    source_vwap is None or jita_vwap is None or
                    profit <= 0 or roi <= 0 or stress <= Policy().profit_floor or capital <= 0 or
                    source_vwap <= 0 or jita_vwap <= 0 or
                    row.get("quantity_optimized") is not True):
                continue
            # Cross-check the quoted VWAP against the actual proof cash flows.
            if (not math.isclose(source_vwap*quantity,
                                 float(row.get("executed_sell_cost") or 0),rel_tol=1e-9) or
                not math.isclose(jita_vwap*quantity,
                                 float(row.get("executed_jita_buy_gross") or 0),rel_tol=1e-9)):
                continue
            cargo=market_volume(row,quantity)
            market.append({
                "type_id":typ,"quantity":quantity,
                **cargo,
                "source_location":source, "destination_location":JITA,
                "net_profit_snapshot":profit,"roi_snapshot":roi,
                "stress_profit_snapshot":stress,
                "capital":capital,"haul_estimate":_amount(row.get("haul_isk")),
                "source_vwap_isk_per_unit":source_vwap,
                "jita_vwap_isk_per_unit":jita_vwap,
                "source_top5_sell":row.get("source_top5_sell"),
                "jita_top5_buy":row.get("jita_top5_buy"),
                "market_url":f"{WORKER}/m/{typ}",
                "live_verified":False,"actionable":False,
            })
    expected=int(report.get("market_proofs_examined",-1))
    if examined != expected:
        raise RuntimeError("MARKET_PROOF_COUNT_MISMATCH")
    # First discovery is NOT reset on repeat scans or changing quantities.
    # Shared by Gmail and both in-game recipients, with one durable local index.
    seen = first_seen(root, folder.name)
    market = order_by_discovery(market, kind="market", seen=seen,
                                fallback_run=folder.name)
    all_contracts=review.get("research_leads") or []
    if exclusion is not None:
        # Defense in depth: even if a caller bypassed contract_review, no
        # excluded hull/blueprint contract can occupy or escape the ten slots.
        verified=[]
        for lead in all_contracts:
            if exclusion.blocks_contract(lead.get("included_items")):
                blocked["contract_post_filter"]+=1
            else:
                verified.append(lead)
        all_contracts=verified
    contracts = order_by_discovery(all_contracts,
                                   kind="contract", seen=seen,
                                   fallback_run=folder.name)
    blueprints = order_by_discovery(blueprints,kind="blueprint",
                                   seen=seen,fallback_run=folder.name)
    cap = max(0, min(int(limit_each), MAX_EACH))
    review.update({
        "report_type":"V4_UNIFIED_MARKET_AND_CONTRACT_REVIEW_ONLY",
        "market_pricing_basis":report["market_pricing_basis"],
        "market_execution_basis":report["market_execution_basis"],
        "market_potential_pairs":int(report.get("market_potential_pairs") or 0),
        "market_proofs_examined":examined,
        "market_rejection_reasons":dict(rejected.most_common(8)),
        "ship_exclusion_policy":POLICY_NAME if exclusion else "LEGACY_FIXTURE_NO_CATALOG",
        "excluded_capital_freighter_market_leads":blocked["market"],
        "excluded_capital_freighter_contract_leads":(
            review.get("excluded_capital_freighter_contract_leads",0)+
            blocked["contract_post_filter"]),
        "excluded_capital_freighter_blueprint_leads":blocked["blueprint_manufacturing"],
        "market_research_leads_total":len(market),
        "market_research_leads":market[:cap],
        "contract_research_leads_total":review.get("research_leads_total",0),
        "contract_research_leads":contracts[:cap],
        "blueprint_research_leads_total":len(blueprints),
        "blueprint_proofs_examined":blueprint_examined,
        "blueprint_research_leads":blueprints[:cap],
        # Legacy shared receipt fields must describe the ACTUALLY displayed
        # contract leads, not the unbounded unsorted source pool.
        "research_leads":contracts[:cap],
    })
    return review


def discovered_label(lead: dict) -> str:
    """Discovery timestamp for both Gmail and EVE, in Beijing local time."""
    stamp = lead.get("first_seen_at")
    if not stamp:
        return ""
    try:
        instant = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        if instant.tzinfo is None:
            return ""
        local = instant.astimezone(timezone(timedelta(hours=8)))
        return " 首见" + local.strftime("%m-%d %H:%M")
    except (ValueError, TypeError, OverflowError):
        return ""


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


def _blueprints(review: dict, good: bool):
    return (review.get("blueprint_research_leads") or [])[:MAX_EACH] if good else []


def _subject(review: dict, pairs: list, contracts: list) -> str:
    time = beijing_scan_time(review.get("run_folder"))
    return f"V4捡漏待核 {time} 市场{len(pairs)} 合同{len(contracts)}"


def render(review: dict, *, game: bool = False) -> tuple[str, str]:
    """Short human-readable body. Game version contains native EVE click targets.

    Important: showinfo opens the item's information, not a particular sell
    order. Contract links open the exact contract identifier in-game.
    """
    pairs, contracts, good = _selected(review)
    blueprints = _blueprints(review,good)
    subject = _subject(review, pairs, contracts) + f" 蓝图制造{len(blueprints)}"
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
                f"{discovered_label(p)}"
                f" 净{yi(p['net_profit_snapshot'])} ROI{p['roi_snapshot']*100:.0f}%"
                f"｜成交均 本地卖{unit_price(p['source_vwap_isk_per_unit'])}"
                f"→吉买{unit_price(p['jita_vwap_isk_per_unit'])}"
                f"｜参考{five_level_label(p, 'source_top5_sell', '卖')}"
                f" / {five_level_label(p, 'jita_top5_buy', '吉买')}"
                f"｜{market_label(p)}")
    if contracts:
        lines.append("【合同】")
        for n, p in enumerate(contracts, 1):
            cid = int(p["contract_id"])
            if game:
                name = f"<url=contract:0//{cid}><b>打开合同 {cid}</b></url>"
            else:
                name = f"合同 {cid} {WORKER}/c/{cid}"
            lines.append(
                f"{n}. {name} {contract_place(p)}"
                f"{discovered_label(p)}"
                f" 价{yi(p.get('contract_price'))}"
                f" 净{yi(p['net_profit_snapshot'])} ROI{p['roi_snapshot']*100:.0f}%"
                f"｜{contract_label(p)}"
                + (f"｜{credited_volume_breakdown(p)}"
                   if credited_volume_breakdown(p) else ""))
    if blueprints:
        lines.append("【蓝图制造（估算研究）】")
        for n, p in enumerate(blueprints,1):
            cid=int(p["contract_id"])
            bpid=int(p["blueprint_type_id"])
            product=int(p["product_type_id"])
            if game:
                label=f"<url=contract:0//{cid}>蓝图合同 {cid}</url>"
            else:
                label=f"蓝图合同 {cid} {WORKER}/c/{cid}"
            lines.append(
                f"{n}. {label} {place(p.get('source_location'))}"
                f" 蓝图{bpid} {p['blueprint_kind']} ×{p['production_runs_assumed']}次"
                f"→成品{product}×{p['product_units']}"
                f"｜净{yi(p['net_profit_snapshot'])} ROI{p['roi_snapshot']*100:.0f}%"
                f"｜成品卖出{yi(p.get('product_gross'))}"
                f" 合同{yi(p.get('contract_price'))}"
                f" 材料{yi(p['material_cost'])}"
                f" 销售税{yi(p.get('sales_tax'))}"
                f" 预留制造费{yi(p['fee_reserve'])}"
                f"（按材料费20%预留；实际设施费、技能、工期未验证）")
    if not pairs and not contracts and not blueprints:
        lines.append("本轮暂无候选。")
    if review.get("npc_catalog_status") == "NOT_INSTALLED_LEGACY_CONTRACT_SCOPE":
        lines.append("注意：NPC高低安目录未安装，本轮合同仍仅覆盖旧站点。")
    lines.append("快照待核，不代表可立即成交。")
    # EVE ESI supports <br>, and actual native in-client <url=...> syntax.
    return subject, ("<br>" if game else "\n").join(lines)


def render_html(review: dict) -> tuple[str, str]:
    """HTML Gmail alternative with real anchors, not plain URL text.

    No remote images, scripts, or unsanitized data from contracts; hrefs
    are created only from validated numeric IDs on our own opener domain.
    """
    pairs, contracts, good = _selected(review)
    blueprints = _blueprints(review,good)
    subject = _subject(review, pairs, contracts) + f" 蓝图制造{len(blueprints)}"
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
                    f'{html.escape(discovered_label(p))}'
                    f' ｜净{yi(p["net_profit_snapshot"])}'
                    f' ｜ROI {float(p["roi_snapshot"])*100:.0f}%'
                    f' ｜成交均 本地卖{unit_price(p["source_vwap_isk_per_unit"])}'
                    f'→吉买{unit_price(p["jita_vwap_isk_per_unit"])}'
                    f' ｜参考{html.escape(five_level_label(p, "source_top5_sell", "卖"))}'
                    f' / {html.escape(five_level_label(p, "jita_top5_buy", "吉买"))}'
                    f' ｜{html.escape(market_label(p))}</p>')
        if contracts:
            blocks.append("<p><strong>合同</strong></p>")
            for n, p in enumerate(contracts, 1):
                cid = int(p["contract_id"])
                place_name = html.escape(contract_place(p))
                blocks.append(
                    f'<p>{n}. <a href="{WORKER}/c/{cid}">打开合同 {cid}</a>'
                    f' {place_name}{html.escape(discovered_label(p))}'
                    f' ｜价{yi(p.get("contract_price"))}'
                    f' ｜净{yi(p["net_profit_snapshot"])}'
                    f' ｜ROI {float(p["roi_snapshot"])*100:.0f}%'
                    f' ｜{html.escape(contract_label(p))}'
                    + (f' ｜{html.escape(credited_volume_breakdown(p))}'
                       if credited_volume_breakdown(p) else '') + '</p>')
        if not pairs and not contracts and not blueprints:
            blocks.append("<p>本轮暂无候选。</p>")
    if blueprints:
        blocks.append('<p><strong>蓝图制造（成本预留估算，非交易核验）</strong></p>')
        for n,b in enumerate(blueprints,1):
            cid=int(b["contract_id"])
            blocks.append(
                f'<p>{n}. <a href="{WORKER}/c/{cid}">合同 {cid}</a>'
                f' 蓝图{int(b["blueprint_type_id"])}'
                f' {html.escape(str(b["blueprint_kind"]))}'
                f' 制造{int(b["production_runs_assumed"])}次'
                f' 成品{int(b["product_type_id"])}×{int(b["product_units"])}'
                f' 净{yi(b["net_profit_snapshot"])}'
                f' ROI{float(b["roi_snapshot"])*100:.0f}%'
                f' 成品卖出{yi(b.get("product_gross"))}'
                f' 合同{yi(b.get("contract_price"))}'
                f' 材料{yi(b["material_cost"])}'
                f' 销售税{yi(b.get("sales_tax"))}'
                f' 制造费用预留{yi(b["fee_reserve"])}'
                '（材料费用20%预留，实际费用、工期、技能未核实）</p>')
    if review.get("npc_catalog_status") == "NOT_INSTALLED_LEGACY_CONTRACT_SCOPE":
        blocks.append('<p>注意：NPC高低安目录未安装，本轮合同仍仅覆盖旧站点。</p>')
    blocks.append('<p style="color:#777;font-size:12px">快照待核，不代表可立即成交。</p>')
    body = ('<!doctype html><html><head><meta charset="utf-8"></head>'
            '<body style="font-family:Arial,sans-serif;font-size:14px;'
            'line-height:1.4">' + "".join(blocks) + '</body></html>')
    return subject, body
