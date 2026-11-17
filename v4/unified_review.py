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
from v4.mail_names import load as load_mail_names, clean as clean_name
from v4.structure_registry import STATIONS as APPROVED_STRUCTURES, LANE_TO_LABEL

JITA = 60003760
WORKER = "https://eve-contract-opener.99617224.workers.dev"
MAX_EACH = 10
# Approved mail rule: net profit >= 50m, ROI > 10%, descending profit.
# ROI and risk may be displayed, but never secretly reweight the ranking.
def research_mail_eligible(lead: dict) -> bool:
    profit = _amount(lead.get("net_profit_snapshot"))
    roi = _amount(lead.get("roi_snapshot"))
    policy = Policy()
    return (profit is not None and profit >= policy.profit_floor and
            roi is not None and roi > policy.min_roi)


def research_profit_sort_key(lead: dict):
    return (-float(lead["net_profit_snapshot"]),
            -float(lead["roi_snapshot"]),
            int(lead.get("contract_id") or lead.get("type_id") or 0))
LOCATION_NAMES = {
    60003760:"吉他4-4", 60008494:"艾玛", 60011866:"多迪谢",
    **{location: name for name, location in APPROVED_STRUCTURES.items()},
}


def place(value) -> str:
    try:
        n = int(value)
    except (ValueError, TypeError, OverflowError):
        return "位置未知"
    return LOCATION_NAMES.get(n, str(n))


def contract_liquidity_label(lead: dict) -> str:
    """Explicitly distinguish historical regional trades from station bid fills."""
    if float(lead.get("contract_history_reference_share") or 0) > 0:
        dates = lead.get("contract_history_reference_dates") or {}
        most_recent = max(dates.values(), default="日期未核实")
        return ("｜风险: 无吉他4-4买单，使用伏尔加星域最近有成交日的"
                "区域日均成交价(" + most_recent + ")；不是吉他最后一笔成交价、"
                "不是即时可兑现价格")
    if float(lead.get("contract_ask_only_reference_share") or 0) > 0:
        return "｜风险: 无吉他买单的商品按卖价上界参考，不代表可成交收入"
    if "JITA_BUY_DEPTH_INSUFFICIENT" in (
            lead.get("contract_liquidity_risk_flags") or []):
        return "｜风险: 吉他买单深度不足，仅参考价估值"
    return ""


def contract_place(lead: dict) -> str:
    """Identify high/low NPC contract pickup without claiming safe transport."""
    source = place(lead.get("source_location"))
    if source in LOCATION_NAMES.values():
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
        return money(amount)
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
    if review.get("contract_pricing_basis") not in (
            "JITA_4_4_BUY_DEPTH_SNAPSHOT",
            "JITA_4_4_REGULAR_REFERENCE_NO_BUY_DEPTH_GATE",
            "JITA_BUY_OR_FORGE_LATEST_TRADED_DAY_AVG_RESEARCH"):
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
                blueprint_examined += 1
                # The BPC strategy has its own provenance, not the old Jita
                # depth-executable valuation. BPO and resale do not enter.
                if (row.get("model_candidate") is True and
                    row.get("status") == "WATCH" and
                    row.get("blueprint_kind") == "BPC" and
                    row.get("valuation_basis") ==
                        "JITA_TOP5_BPC_MANUFACTURE_30PCT_BUNDLE_ESTIMATE" and
                    row.get("facility_fee_status") ==
                        "ESI_ADJUSTED_PRICES_SYSTEM_COST_INDEX_JITA_NPC_REFERENCE_NOT_JOB_QUOTE" and
                    row.get("manufacturing_fee_snapshot_verified") is True and
                    row.get("jita_material_top5_prices_observed") is True and
                    row.get("jita_product_top5_prices_observed") is True):
                    net = _amount(row.get("net_profit"))
                    roi = _amount(row.get("roi"))
                    risk = _amount(row.get("risk_score"))
                    if (net is not None and net >= 50_000_000 and
                        roi is not None and roi > .10 and
                        risk is not None and 0 <= risk <= 100):
                        selected = row.get("bundle_selected_details") or []
                        if not isinstance(selected, list) or not selected:
                            continue
                        if (exclusion is not None and any(
                            exclusion.blocks_blueprint(
                                x.get("blueprint_type_id"), x.get("product_type_id"))
                            for x in selected)):
                            blocked["blueprint_manufacturing"] += 1
                            continue
                        lead = {
                            "contract_id": row.get("contract_id"),
                            "blueprint_type_id": row.get("blueprint_type_id"),
                            "blueprint_kind": "BPC",
                            "production_runs_assumed": row.get("production_runs_assumed"),
                            "product_type_id": row.get("product_type_id"),
                            "product_units": row.get("product_units"),
                            "bundle_blueprint_total": row.get("bundle_blueprint_total"),
                            "bundle_blueprint_selected": row.get("bundle_blueprint_selected"),
                            "bundle_selected_type_ids": row.get("bundle_selected_type_ids"),
                            "bundle_selected_details": selected,
                            "contract_price": row.get("contract_price_isk"),
                            "product_gross": row.get("product_gross_isk"),
                            "material_cost": row.get("material_cost_isk"),
                            "fee_reserve": row.get("manufacturing_fee_isk"),
                            "investment": row.get("cost"),
                            "haul_estimate_isk": row.get("haul_estimate_isk"),
                            "manufacturing_fee_status": row.get("facility_fee_status"),
                            "manufacturing_fee_observed_at_utc": row.get("manufacturing_fee_observed_at_utc"),
                            "sales_tax": row.get("sales_tax_isk"),
                            "net_profit_snapshot": net,
                            "roi_snapshot": roi,
                            "risk_score": risk,
                            "risk_flags": row.get("risk_flags") or [],
                            "source_location": row.get("source_location"),
                            "cost_basis": "Jita top-five distinct price mean + ESI manufacturing reference fee; not depth executable",
                            "live_verified": False,
                            "actionable": False,
                        }
                        # Risk still appears in mail, never in ordering.
                        blueprints.append(lead)
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
                    profit < Policy().profit_floor or roi <= Policy().min_roi or
                    stress <= Policy().profit_floor or capital <= 0 or
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
                "purchase_total":_amount(row.get("executed_sell_cost")),
                "gross_sale":_amount(row.get("executed_jita_buy_gross")),
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
    market = [lead for lead in market if research_mail_eligible(lead)]
    market.sort(key=research_profit_sort_key)
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
    contracts = [lead for lead in contracts if research_mail_eligible(lead)]
    contracts.sort(key=research_profit_sort_key)
    blueprints = order_by_discovery(blueprints, kind="blueprint",
                                   seen=seen, fallback_run=folder.name)
    blueprints = [lead for lead in blueprints if research_mail_eligible(lead)]
    blueprints.sort(key=research_profit_sort_key)
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
    review["mail_names"] = _select_names(load_mail_names(root), review)
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


def _coverage_alert(review: dict) -> tuple[str, str]:
    """Never call an incomplete scan zero opportunities.

    Only trusted, fixed lane labels and recorded status values are displayed.
    No ESI credentials, worker error payloads or market candidates are shown.
    """
    names = LANE_TO_LABEL
    health = review.get("structure_health") or {}
    failed = [label for lane, label in names.items()
              if health.get(lane) != "COMPLETE"]
    detail = "、".join(failed) if failed else "数据源完整性未通过"
    when = beijing_scan_time(review.get("run_folder"))
    subject = f"【EVE V4采集故障】{when} {detail}｜机会判断已暂停"
    body = ("本轮采集数据不完整，所有市场、合同和蓝图制造机会均已暂停推送。"
            "这不是零机会，不能据此判断市场没有利润。"
            f"\n采集异常：{detail}。"
            "\n请核查本机最近一次 manifest.json 的 failed_structure_lanes "
            "及 structure_health 字段。")
    return subject, body


def _select_names(names, review):
    """Retain only the names required for this digest, never the full SDE."""
    types, stations = set(), set()
    for lead in review.get("market_research_leads") or []:
        types.add(str(lead.get("type_id")))
        stations.add(str(lead.get("source_location")))
    for lead in review.get("contract_research_leads") or []:
        types.update(str(k) for k in (lead.get("included_items") or {}))
        types.update(str(d.get("type_id")) for d in lead.get("credited_volume_items") or [])
        stations.add(str(lead.get("source_location")))
    for lead in review.get("blueprint_research_leads") or []:
        types.add(str(lead.get("blueprint_type_id")))
        types.update(str(d.get("blueprint_type_id")) for d in lead.get("bundle_selected_details") or [])
        stations.add(str(lead.get("source_location")))
    return {kind:{k:names[kind][k] for k in keys if k in names.get(kind,{})}
            for kind,keys in (("types",types),("stations",stations))}


def money(value):
    """Human-readable ISK amounts, including negative and sub-million values."""
    n = _amount(value)
    if n is None:
        return "未核实"
    if abs(n) >= 100_000_000:
        return f"{n/100_000_000:,.2f}".rstrip("0").rstrip(".")+"亿"
    if abs(n) >= 10_000:
        return f"{n/10_000:,.2f}".rstrip("0").rstrip(".")+"万"
    return f"{n:,.2f}".rstrip("0").rstrip(".")+" ISK"


def _display_name(review, tid, limit=70):
    names = (review.get("mail_names") or {}).get("types") or {}
    name = clean_name(names.get(str(tid)))
    if not name or name.isdigit():
        return "物品名称待核实"
    return name if len(name)<=limit else name[:limit-1]+"…"


def _location(review, lead, limit=80):
    key = str(lead.get("source_location"))
    try:
        station = LOCATION_NAMES.get(int(key))
    except (TypeError, ValueError):
        station = None
    if not station:
        station = clean_name(((review.get("mail_names") or {}).get("stations") or {}).get(key))
    if not station:
        station = clean_name(lead.get("source_station_name"))
    if not station or station.isdigit():
        station = "空间站名称待核实"
    prefix = {"HIGH":"高安","LOW":"低安"}.get(lead.get("source_security_band"),"")
    return (prefix+" " if prefix else "")+station[:limit]


def _summary(lead):
    roi = _amount(lead.get("roi_snapshot"))
    return "预计净赚 "+money(lead.get("net_profit_snapshot"))+"｜回报率 "+(
        f"{roi*100:.1f}".rstrip("0").rstrip(".")+"%" if roi is not None else "未核实")


def _items(review, lead, limit):
    items = lead.get("included_items") or {}
    credited = lead.get("credited_items") or {}
    if not isinstance(items,dict):
        return []
    # Credit-bearing goods first. No valuation of ignored items is implied.
    volume = {str(d.get("type_id")):(_amount(d.get("subtotal_volume_m3")) or 0)
              for d in lead.get("credited_volume_items") or []}
    ordered = sorted(items.items(),key=lambda x:(str(x[0]) not in credited and x[0] not in credited,
                                                  -volume.get(str(x[0]),0),-int(x[1]),str(x[0])))
    return [(_display_name(review,t,limit),q) for t,q in ordered]


def _contract_description(review, lead, limit):
    items = _items(review,lead,limit)
    if not items:
        return "物品合同", "内容待核实"
    title = items[0][0]+("等物品合同" if len(items)>1 else "合同")
    details = "、".join(f"{name}×{q}" for name,q in items[:3])
    if len(items)>3:
        details += f"；另{len(items)-3}类"
    return title,details


def _blueprint_description(review, lead, limit):
    # A selected entry can represent more than one physical copy. Group
    # actual recorded licensed production runs by type, not by entry count.
    groups = {}
    details = lead.get("bundle_selected_details") or []
    for item in details:
        typ = item.get("blueprint_type_id")
        runs = _amount(item.get("production_runs"))
        contribution = _amount(item.get("contribution_isk"))
        if typ is None or runs is None or runs <= 0 or contribution is None:
            continue
        before = groups.get(typ,(0,0.))
        groups[typ] = (before[0]+int(runs),before[1]+contribution)
    ranked = sorted(groups.items(),key=lambda x:(-x[1][1],str(x[0])))
    if ranked:
        name = _display_name(review,ranked[0][0],limit)
        text = "、".join(f"{_display_name(review,t,limit)}×{v[0]:,}次"
                         for t,v in ranked[:3])
        if len(ranked)>3:
            text += f"；另{len(ranked)-3}种"
        total = sum(v[0] for v in groups.values())
        if len(details)==sum(1 for d in details if
                d.get("blueprint_type_id") is not None and
                (_amount(d.get("production_runs")) or 0)>0 and
                _amount(d.get("contribution_isk")) is not None):
            count = f"组合制造{total:,}次"
        else:
            count = "组合总次数未核实"
        return name+("等组合" if len(ranked)>1 else "组合"),count,text
    name = _display_name(review,lead.get("blueprint_type_id"),limit)
    runs = _amount(lead.get("production_runs_assumed"))
    return name+"组合","组合总次数未核实",(
        f"代表蓝图{int(runs):,}次" if runs is not None else "制造次数未核实")


def _risk_text(lead):
    flags = lead.get("risk_flags") or []
    labels = {"LESS_THAN_FIVE_PRICE_LEVELS":"报价档数不足",
              "SNAPSHOT_DEPTH_BELOW_MODEL_QUANTITY":"买卖深度不足",
              "BPC_VALUE_MISSING_IN_BUNDLE":"部分蓝图未估值",
              "MANUFACTURING_FEE_NOT_ESI_VERIFIED":"制造费未核实"}
    risk = _amount(lead.get("risk_score"))
    text = "模型风险 "+(f"{risk:.0f}/100" if risk is not None else "未核实")
    reasons = [v for k,v in labels.items() if k in flags]
    return text+("；"+"、".join(reasons) if reasons else "")


def _entry(review, kind, lead, compact=False):
    lim = 12 if compact == 2 else 18 if compact else 45
    loc = _location(review,lead,20 if compact == 2 else 30 if compact else 80)
    discovered = discovered_label(lead).strip()
    head = _summary(lead)
    if kind == "market":
        name = _display_name(review,lead.get("type_id"),lim)+f" ×{int(lead['quantity']):,}"
        link = ("m",int(lead["type_id"]))
        lines = [head,
                 f"采购：{loc}｜投入 {money(lead.get('capital'))}",
                 f"单价 买{money(lead.get('source_vwap_isk_per_unit'))} → 吉他卖{money(lead.get('jita_vwap_isk_per_unit'))}",
                 market_label(lead)]
        if not compact:
            lines.append("采购货款 "+money(lead.get("purchase_total"))+"｜销售额 "+
                         money(lead.get("gross_sale"))+"｜运费 "+money(lead.get("haul_estimate")))
            lines.append("参考 "+five_level_label(lead,"source_top5_sell","本地卖")+
                         " / "+five_level_label(lead,"jita_top5_buy","吉他买"))
    elif kind == "contract":
        name,contents = _contract_description(review,lead,lim)
        link = ("c",int(lead["contract_id"]))
        lines = [head,
                 f"采购：{loc}｜合同价 {money(lead.get('contract_price'))}",
                 f"投入 {money(lead.get('investment'))}｜运费 {money(lead.get('haul_estimate_isk'))}",
                 "合同包含："+contents,
                 contract_label(lead)]
        if not compact:
            details = lead.get("credited_volume_items") or []
            if details:
                from v4.mail_volume import format_m3
                lines.append("计价货物："+"；".join(
                    f"{_display_name(review,d.get('type_id'),lim)}×{d['quantity']} 单件{format_m3(d.get('unit_volume_m3'))} 小计{format_m3(d.get('subtotal_volume_m3'))}"
                    for d in details[:3]))
            risk = contract_liquidity_label(lead).lstrip("｜")
        else:
            risk = ""
            if float(lead.get("contract_history_reference_share") or 0)>0:
                risk = "风险：无吉他买单，采用伏尔加星域历史成交参考，非即时成交"
            elif float(lead.get("contract_ask_only_reference_share") or 0)>0:
                risk = "风险：卖价参考，非可成交收入"
            elif "JITA_BUY_DEPTH_INSUFFICIENT" in (lead.get("contract_liquidity_risk_flags") or []):
                risk = "风险：吉他买单深度不足"
        if risk:
            lines.append(risk)
    else:
        name,count,details = _blueprint_description(review,lead,lim)
        link = ("c",int(lead["contract_id"]))
        lines = [head,
                 f"采购：{loc}｜投入 {money(lead.get('investment'))}",
                 f"蓝图 {money(lead.get('contract_price'))}｜材料 {money(lead.get('material_cost'))}｜制造费 {money(lead.get('fee_reserve'))}",
                 f"运费 {money(lead.get('haul_estimate_isk'))}｜销售税 {money(lead.get('sales_tax'))}｜销售额 {money(lead.get('product_gross'))}",
                 f"BPC选中{lead.get('bundle_blueprint_selected') or 1}/{lead.get('bundle_blueprint_total') or 1}条｜{count}",
                 details, _risk_text(lead)]
    if compact == 2:
        if kind == "contract":
            # Keep all candidates and their price, profit, location, costs and
            # risk. Long item lists remain in the full Gmail digest.
            lines[3] = "合同包含："+(contents.split("、")[0].split("；")[0])+"（详见Gmail）"
        elif kind == "blueprint":
            lines[5] = details.split("、")[0].split("；")[0]+"（详见Gmail）"
    elif discovered:
        lines.append("首次发现 "+discovered.replace("首见","",1))
    return name,link,lines


def _sections(review, compact=False):
    pairs, contracts, good = _selected(review)
    bps = _blueprints(review,good)
    subject = _subject(review,pairs,contracts)+f" 蓝图制造{len(bps)}"
    if not good:
        subject,alert = _coverage_alert(review)
        return subject, [], [alert]
    sections = [(label,[_entry(review,kind,p,compact) for p in leads])
                for label,kind,leads in (("市场","market",pairs),("合同","contract",contracts),
                                        ("蓝图制造","blueprint",bps)) if leads]
    notes = []
    if not sections:
        notes.append("本轮暂无候选。")
    if sections and not (review.get("mail_names") or {}).get("types"):
        notes.append("当前机会名称未核实，请安装或更新官方SDE名称字典。")
    if review.get("npc_catalog_status")=="NOT_INSTALLED_LEGACY_CONTRACT_SCOPE":
        notes.append("注意：NPC高低安目录未安装，本轮合同仍仅覆盖旧站点。")
    if pairs or contracts:
        notes.append("体积按打包估算；已组装舰船以游戏内为准。")
    if bps:
        notes.append("蓝图为吉他前5档均价制造估算；投入不含销售税，未计制造时间、资金占用及销售周期；风险分0不等于无风险。")
    notes.append("快照待核，不代表可立即成交。")
    return subject,sections,notes


def render(review: dict, *, game: bool = False) -> tuple[str, str]:
    """Shared native EVE and plain-text layout. IDs appear only in link targets."""
    def build(compact):
        subject,sections,notes = _sections(review,compact)
        lines = []
        for label,entries in sections:
            lines.append("【"+label+"】")
            for n,(name,(kind,ident),details) in enumerate(entries,1):
                if game:
                    target = f"showinfo:{ident}" if kind=="m" else f"contract:0//{ident}"
                    title = f"<url={target}><b>{html.escape(name)}</b></url>"
                else:
                    title = f"{name} {WORKER}/{kind}/{ident}"
                lines.append(f"{n}. {title}")
                lines.extend(html.escape(x) if game else x for x in details)
                if not compact:
                    lines.append("")
        lines.extend(html.escape(x).replace("\n","<br>") if game else x for x in notes)
        return subject, ("<br>" if game else "\n").join(lines)
    subject,body=build(False)
    if game and len(body)>9000:
        subject,body=build(True)
    if game and len(body)>9000:
        subject,body=build(2)
    # No truncation of native links or removal of any candidate.
    if game and len(body)>9000:
        raise RuntimeError("GAME_MAIL_DIGEST_TOO_LONG")
    return subject,body


def render_html(review: dict) -> tuple[str, str]:
    subject,sections,notes = _sections(review)
    blocks=[]
    for label,entries in sections:
        blocks.append(f"<h3>{html.escape(label)}</h3>")
        for n,(name,(kind,ident),details) in enumerate(entries,1):
            blocks.append(f'<p>{n}. <a href="{WORKER}/{kind}/{ident}">{html.escape(name)}</a>'
                          f'<br><strong>{html.escape(details[0])}</strong>'
                          +"".join("<br>"+html.escape(x) for x in details[1:])+"</p>")
    blocks.extend("<p>"+html.escape(x).replace("\n","<br>")+"</p>" for x in notes)
    body=('<!doctype html><html><head><meta charset="utf-8"></head>'
          '<body style="font-family:Arial,sans-serif;font-size:14px;line-height:1.4">'
          +"".join(blocks)+"</body></html>")
    return subject,body
