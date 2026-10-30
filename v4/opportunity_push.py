"""V4 autonomous hourly opportunity-notification lane for a Windows host.

Fetches complete official ESI Forge, Domain, and Sinq Laison books plus the
approved authenticated private structure books. Failed NPC coverage is reported
and omitted; it never suppresses otherwise valid private-structure alerts. Reuses the unmodified
V4 market execution engine, the existing Windows credential vault, and the
existing game mail worker/Gmail sender. No buy/sell/contract action.

Notifications are FRESH SNAPSHOT LEADS requiring in-game order/route check,
not verified guaranteed executable trades. Fail closed on missing lanes,
stale ESI, missing auth, or unverified transport data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from pathlib import Path

from v4.catalog import Catalog, DEFAULT_CACHE
from v4.esi_private_source_jita_ab import (
    _fresh_jita_books, _fetch_authorized_once, _private_asks, _evaluate,
    ParityError, STRUCTURES, JITA, POLICY
)
from v4.market_depth import top_price_levels
from v4.local_run import exclusive_lock

PUSH_STATE="opportunity-push/state.json"
SUPPRESS_HOURS=12
MAX_MAIL_ITEMS=8


def _utcnow():
    return datetime.now(timezone.utc)


def _atomic(path,doc):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".json.part")
    try:
        temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2,
                                   allow_nan=False),encoding="utf-8")
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)


def _state(root):
    p=Path(root)/PUSH_STATE
    if not p.is_file():
        return {"schema":1,"channels":{}}
    doc=json.loads(p.read_text(encoding="utf-8"))
    if (doc.get("schema")!=1 or
            not isinstance(doc.get("channels"),dict)):
        raise RuntimeError("OPPORTUNITY_PUSH_STATE_INVALID")
    return doc


def _signature(p):
    """Dedup same item, location, quantity and model price/cost structure."""
    signal=[p["station"],p["type_id"],p["quantity"],
            round(p["source_vwap_isk"],2),
            round(p["jita_buy_vwap_isk"],2),
            round(p["net_profit_isk"],2)]
    return hashlib.sha256(json.dumps(signal,separators=(",",":")).encode()).hexdigest()[:32]


def _record_candidate(p,asks,jita):
    loc=p["station_id"]
    typ=p["type_id"]
    source=asks.get((loc,typ,False)) or []
    buy=jita.get((JITA,typ,True)) or []
    if not source or not buy:
        raise RuntimeError("ACCEPTED_BOOK_SUDDENLY_MISSING")
    source5=top_price_levels(source,buy=False)
    buy5=top_price_levels(buy,buy=True)
    return {
        **p,"signal_key":_signature(p),
        "source_sell_top5_mean":source5["simple_mean_isk_per_unit"],
        "source_sell_top5_levels":source5["group_count"],
        "jita_buy_top5_mean":buy5["simple_mean_isk_per_unit"],
        "jita_buy_top5_levels":buy5["group_count"],
        "stress_minus_profit_floor_isk":p["stress_profit_isk"]-POLICY.profit_floor,
    }


def _current_opportunities(root,*,run_esi=None,fetch_private=None,catalog=None,
                           haul_fn=None,now=None):
    from v4.npc_market_opportunity import (
        REGIONS, NPC_REGIONS, fresh_public_books, evaluate_npc)
    from v4.structure_registry import LANE_TO_LABEL
    root=Path(root)
    start=now or _utcnow()
    if catalog is None:
        if not DEFAULT_CACHE.is_file():
            raise RuntimeError("LOCAL_V4_CATALOG_MISSING")
        catalog=Catalog.load(DEFAULT_CACHE)
    default_esi=run_esi is None
    if default_esi:
        from v4.esi_parallel_validation import run
        def run_esi():
            return run(root,max_workers=3,max_regions=None,
                       fetch_reference=False,
                       region_ids_override=list(REGIONS))
    snapshot,folder=run_esi()

    if fetch_private is None:
        fetch_private=_fetch_authorized_once
    raw,health=fetch_private()
    private_finished=_utcnow() if now is None else now
    asks,counts,hashes=_private_asks(raw,health)
    if not asks:
        raise ParityError("NO_AUTHORIZED_SELL_ORDERS")

    # Official public books only. Never treat a failed NPC regional census
    # as a verified "no opportunities" result or use stale EVE Ref quotes.
    npc_asks={}
    npc_health={name:{"status":"NOT_CAPTURED"}
                for name,_ in NPC_REGIONS.values()}
    multi=(snapshot.get("status")=="PARTIAL_REGION_TEST_ONLY"
           and snapshot.get("requested_region_ids")==list(REGIONS)
           and len(snapshot.get("regions") or [])==len(REGIONS))
    if multi:
        try:
            jita,npc_asks,jita_evidence,npc_health=fresh_public_books(
                root,snapshot,now=private_finished)
        except (ParityError,ValueError,OSError) as exc:
            if not default_esi:
                raise
            # A newly added NPC region cannot take down the existing
            # 4-structure notification lane. Recapture Forge alone, fail
            # CLOSED for NPC, and surface source health to operators.
            npc_health={name:{"status":"FAILED","reason":type(exc).__name__}
                        for name,_ in NPC_REGIONS.values()}
            rescue,_=run(root,max_workers=1,max_regions=None,
                         fetch_reference=False,
                         region_ids_override=[10000002])
            if (rescue.get("status")!="PARTIAL_REGION_TEST_ONLY"
                    or rescue.get("requested_region_ids")!=[10000002]
                    or rescue.get("failed_regions")
                    or rescue.get("unverified_404_regions")):
                raise ParityError("NPC_FAILURE_AND_FORGE_RECAPTURE_FAILED")
            private_finished=_utcnow()
            jita,_,jita_evidence=_fresh_jita_books(
                root,rescue["run"],now=private_finished)
            snapshot=rescue
    else:
        if default_esi:
            npc_health={name:{"status":"FAILED","reason":"NPC_ESI_REGION_CAPTURE_FAILED"}
                        for name,_ in NPC_REGIONS.values()}
            rescue,_=run(root,max_workers=1,max_regions=None,
                         fetch_reference=False,
                         region_ids_override=[10000002])
            if (rescue.get("status")!="PARTIAL_REGION_TEST_ONLY"
                    or rescue.get("requested_region_ids")!=[10000002]
                    or rescue.get("failed_regions")
                    or rescue.get("unverified_404_regions")):
                raise ParityError("NPC_FAILURE_AND_FORGE_RECAPTURE_FAILED")
            private_finished=_utcnow()
            jita,_,jita_evidence=_fresh_jita_books(
                root,rescue["run"],now=private_finished)
            snapshot=rescue
        else:
            # Legacy injected single-region fixture remains private-only;
            # it never silently activates NPC trading.
            if (snapshot.get("status")!="PARTIAL_REGION_TEST_ONLY"
                    or snapshot.get("requested_region_ids")!=[10000002]
                    or (snapshot.get("regions") or [{}])[0].get("status")!="COMPLETE"):
                raise ParityError("NPC_ESI_UNVERIFIED_CAPTURE")
            jita,_,jita_evidence=_fresh_jita_books(
                root,snapshot["run"],now=private_finished)

    if haul_fn is None:
        from v4.deep_scan import haul, known_station_regions
        stations=known_station_regions() if npc_asks else {}
        haul_fn=lambda src,dest,volume:haul(src,dest,volume,stations)

    evaluated,model_counts,by_station=_evaluate(asks,jita,catalog,haul_fn)
    all_asks=dict(asks)
    npc_model_counts={}
    if npc_asks:
        npc_evaluated,npc_model_counts,npc_by_station=evaluate_npc(
            npc_asks,jita,catalog,haul_fn)
        evaluated.update(npc_evaluated)
        all_asks.update(npc_asks)
        by_station.update(npc_by_station)
    for name,_ in NPC_REGIONS.values():
        by_station.setdefault(name,{"sell_types":0})
    passing=[]
    for p in evaluated.values():
        if p["hypothetical_model_pass"]:
            if (p["net_profit_isk"] is None or
                    p["stress_profit_isk"] is None or
                    p["net_profit_isk"]<POLICY.profit_floor or
                    p["roi"]<POLICY.min_roi or
                    p["stress_profit_isk"]<=POLICY.profit_floor):
                raise RuntimeError("MODEL_PASS_POLICY_INCONSISTENT")
            passing.append(_record_candidate(p,all_asks,jita))
    passing.sort(key=lambda p:(-p["net_profit_isk"],p["station"],p["type_id"]))
    source_lanes=[LANE_TO_LABEL.get(name,name)
                  for name,item in health.items() if item["status"]=="COMPLETE"]
    source_lanes+=sorted(name for name,item in npc_health.items()
                         if item["status"]=="COMPLETE")
    jita_evidence={**jita_evidence,"source_lanes":source_lanes,
                   "npc_source_health":npc_health}
    return {
        "status":"FRESH_ESI_PRIVATE_MARKET_SHADOW_LEADS",
        "run":snapshot["run"],
        "started_at":start.isoformat(),
        "finished_at":private_finished.isoformat(),
        "esi_jita":jita_evidence,
        "npc_source_health":npc_health,
        "authenticated_structure_health":{
            n:{"status":x["status"],"orders":x["orders"],"pages":x["pages"]}
            for n,x in health.items()},
        "private_order_counts":counts,
        "private_fingerprints":hashes,
        "model_counts":model_counts,
        "npc_model_counts":npc_model_counts,
        "by_station":by_station,
        "approved_leads":passing,
        "leads_count":len(passing),
        "model":"UNMODIFIED_V4_market_proof_and_haul",
        "min_profit_isk":POLICY.profit_floor,
        "min_roi":POLICY.min_roi,
        "warning":"Complete fresh official ESI snapshot valuation, not live guaranteed executable. Check source/Jita orders, access and transport before buying.",
    }


def _format_money(v):
    return f"{float(v)/1e6:,.2f}m ISK"


def _digest(leads,evidence,*,game):
    when=_utcnow().astimezone().strftime("%m-%d %H:%M")
    subject=f"EVE V4 市场机会 {len(leads)}组 | {when} | 下单前复核"
    lines=[
        "EVE V4 吉他买单深度机会提醒（模型通过，交易前必须复核）",
        "估值：官方 ESI 吉他4-4实际买单深度；已扣销售税与模型运输费。",
        f"吉他市场快照：{evidence['last_modified']}，"
        f"延迟{evidence['age_at_private_comparison_minutes']:.1f}分钟",
        "卖单来源：" + "、".join(evidence.get("source_lanes") or
                                ["已授权玩家建筑"]) + "，完整分页快照。",
        "筛选：净利≥5000万、ROI≥10%、ISK/m3≥2000、最优吉他买单消失后压力净利>5000万。",
        "注意：运输费用只是V4模型估算，不代表实际运输报价；请在游戏中复核。",
        "NPC采集：" + "、".join(name + "=" + info.get("status","UNKNOWN")
            for name,info in (evidence.get("npc_source_health") or {}).items()),
        "",
    ]
    for index,p in enumerate(leads[:MAX_MAIL_ITEMS],1):
        item=(f"<url=showinfo:{p['type_id']}>物品{p['type_id']}</url>"
              if game else f"物品 {p['type_id']}")
        lines.extend([
            f"{index}. {p['station']} / {item} ×{p['quantity']}",
            f"   净利 {_format_money(p['net_profit_isk'])} | "
            f"ROI {p['roi']*100:.2f}% | "
            f"压力利润 {_format_money(p['stress_profit_isk'])}",
            f"   本地成交均价 {p['source_vwap_isk']:,.2f} | "
            f"吉他买单成交均价 {p['jita_buy_vwap_isk']:,.2f}",
            f"   本地卖5档均价 {p['source_sell_top5_mean']:,.2f} "
            f"({p['source_sell_top5_levels']}档) | "
            f"吉他买5档均价 {p['jita_buy_top5_mean']:,.2f} "
            f"({p['jita_buy_top5_levels']}档)",
            f"   运费估算 {_format_money(p['haul_isk'])}",
            "",
        ])
    if len(leads)>MAX_MAIL_ITEMS:
        lines.append(f"其余{len(leads)-MAX_MAIL_ITEMS}组本轮候选已留在本机摘要。")
    lines.append("本邮件仅用于机会发现，不构成已锁定报价或保证可以成交。")
    return subject,("<br>" if game else "\n").join(lines)


def _send_game(root,run_name,leads,evidence,*,settings=None,session=None,
               get_key=None):
    from v4.game_mail_review import (
        read_settings, enable, add_recipient, _one_game_mail,
        _recipient_receipt,
        WORKER_URL, EXPECTED_SENDER, EXPECTED_SENDER_ID, GameMailTestError,
        _get_bridge_credential, _request_json
    )
    from requests import Session
    config=settings if settings is not None else read_settings(root)
    if not config and settings is None:
        # This user explicitly approved normal opportunity push for both
        # characters. The existing module validates MikeChong's fixed ID.
        enable(root,recipient="MikeChong")
        config=read_settings(root)
    if config and settings is None:
        present={r["name"] for r in config["recipients"]}
        if "MikeChong" in present and "LadyBaBa" not in present:
            # Runtime official exact-name resolution; never invent character IDs.
            add_recipient(root,recipient="LadyBaBa")
            config=read_settings(root)
    if not config:
        return {"status":"GAME_MAIL_NOT_CONFIGURED","sent":False}
    recipients=config["recipients"]
    pending=[r for r in recipients if not any(p.exists()
             for p in _recipient_receipt(root,run_name,r))]
    if not pending:
        return {"status":"GAME_MAIL_ALREADY_SENT","sent":False}
    client=session or Session()
    key=_get_bridge_credential(get_key)
    headers={"Authorization":"Bearer "+key,
             "User-Agent":"EVE V4 opportunity candidate local notifier"}
    status,health=_request_json(client,"GET",WORKER_URL+"/api/mail-health",
                                 headers=headers,timeout=30)
    if (status!=200 or health.get("ok") is not True or
            health.get("sender_name")!=EXPECTED_SENDER or
            health.get("sender_id")!=EXPECTED_SENDER_ID):
        raise GameMailTestError("GAME_MAIL_SENDER_NOT_VERIFIED")
    subject,body=_digest(leads,evidence,game=True)
    if len(body)>9000:
        raise RuntimeError("OPPORTUNITY_GAME_MAIL_TOO_LONG")
    success=[]
    failed=[]
    for user in pending:
        try:
            success.append(_one_game_mail(root,run_name,user,client,headers,
                                          subject[:180],body))
        except (GameMailTestError,OSError) as exc:
            failed.append({"recipient":user["name"],"error_type":type(exc).__name__})
    return {"status":"GAME_MAIL_SENT" if not failed else "GAME_MAIL_PARTIAL_FAILURE",
            "sent":any(p.get("sent") for p in success),
            "recipients":success,"failed":failed}


def _send_gmail(root,run_name,leads,evidence,*,config=None,
                vault=None,smtp_factory=None):
    from v4.research_mail import _config, _windows_keyring, _send_review_smtp, SERVICE
    root=Path(root)
    cfg=config if config is not None else _config(root)
    if not cfg:
        return {"status":"GMAIL_NOT_CONFIGURED","sent":False}
    receipt=root/"opportunity-push"/"gmail-receipts"/(run_name+".json")
    if receipt.is_file():
        return {"status":"GMAIL_ALREADY_SENT","sent":False}
    keyring=vault or _windows_keyring()
    password=keyring.get_password(SERVICE,cfg["sender"])
    if not password:
        raise RuntimeError("OPPORTUNITY_GMAIL_CREDENTIAL_MISSING")
    subject,body=_digest(leads,evidence,game=False)
    msg=EmailMessage()
    msg["From"]=cfg["sender"]
    msg["To"]=cfg["recipient"]
    msg["Subject"]=subject
    msg["Message-ID"]=f"<v4-opportunity-{run_name}@gmail.com>"
    msg.set_content(body)
    # Shared guarded SMTP delivery: tolerate EOF on QUIT *after* Gmail
    # accepted DATA; never retry an ambiguous in-flight send.
    _send_review_smtp(msg, cfg["sender"], password,
                      smtp_factory=smtp_factory)
    _atomic(receipt,{"sent_at":_utcnow().isoformat(),"run":run_name})
    return {"status":"GMAIL_SENT","sent":True}


def run_once(root,*,now=None,build=None,send_game=None,send_gmail=None):
    root=Path(root).resolve()
    with exclusive_lock(root/"v4-local-shadow.lock"):
        now=now or _utcnow()
        # Never read old opportunity reports and pretend they are current.
        dataset=(build or (lambda:_current_opportunities(root)))()
        if dataset.get("status")!="FRESH_ESI_PRIVATE_MARKET_SHADOW_LEADS":
            raise RuntimeError("OPPORTUNITY_LANE_NOT_FRESH")
        signals=dataset["approved_leads"]
        state=_state(root)
        channels=state["channels"]
        current={}
        for p in signals:
            current[p["signal_key"]]=p
        recent={}
        for channel,mapping in channels.items():
            if not isinstance(mapping,dict):
                raise RuntimeError("OPPORTUNITY_PUSH_STATE_INVALID")
            recent[channel]={}
            for sig,stamp in mapping.items():
                try:
                    age=(now-datetime.fromisoformat(stamp)).total_seconds()
                    if -120<=age<SUPPRESS_HOURS*3600:
                        recent[channel][sig]=stamp
                except (ValueError,TypeError):
                    raise RuntimeError("OPPORTUNITY_PUSH_STATE_INVALID")
        sender_game=send_game or (lambda **kw:_send_game(root,**kw))
        sender_gmail=send_gmail or (lambda **kw:_send_gmail(root,**kw))
        statuses={}
        summary_root=root/"opportunity-push"
        summary_root.mkdir(parents=True,exist_ok=True)
        for channel,func in (("game",sender_game),("gmail",sender_gmail)):
            known=recent.setdefault(channel,{})
            novel=[p for sig,p in current.items() if sig not in known]
            if not novel:
                statuses[channel]={"status":"NO_NEW_QUALIFIED_LEADS","sent":False}
                continue
            # Stable per-alert ID across repeated scans prevents duplicate
            # game mail Worker idempotency and local Gmail receipts.
            digest=hashlib.sha256((",".join(sorted(
                p["signal_key"] for p in novel))+":"+channel).encode()).hexdigest()[:24]
            run_name="esi-market-"+digest
            try:
                outcome=func(run_name=run_name,leads=novel,
                             evidence=dataset["esi_jita"])
            except Exception as exc:
                # One dead delivery channel must not suppress the other.
                # Never write exception bodies containing HTTP/SMTP secrets.
                outcome={"status":"OPPORTUNITY_CHANNEL_FAILED",
                         "sent":False,"error_type":type(exc).__name__}
            statuses[channel]=outcome
            # Partial game-mail success must remain retryable for LadyBaBa
            # or MikeChong; successful users have their own worker receipts.
            if (outcome.get("status") in (
                    "GAME_MAIL_SENT","GMAIL_SENT",
                    "GAME_MAIL_ALREADY_SENT","GMAIL_ALREADY_SENT")):
                for p in novel:
                    known[p["signal_key"]]=now.isoformat()
                _atomic(root/PUSH_STATE,{"schema":1,"channels":recent})
        brief={k:v for k,v in dataset.items() if k!="approved_leads"}
        brief.update({
            "status":"OPPORTUNITY_NOTIFICATION_CYCLE_COMPLETE",
            "notification_channels":statuses,
            "qualified_model_leads":len(signals),
            "candidate_preview":signals[:MAX_MAIL_ITEMS],
            "production_source_switch":False,
            "retired_v3_restart":False,
            "contract_scanner_modified":False,
            "mail_presents_live_executable_as_proven":False,
        })
        path=summary_root/(now.strftime("%Y%m%dT%H%M%SZ")
                           +"-"+dataset["run"]+".json")
        _atomic(path,brief)
        return brief,path


def main():
    p=argparse.ArgumentParser(description="V4 authorized private market + fresh Jita ESI recurring candidate notifier")
    p.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    args=p.parse_args()
    summary,path=run_once(args.data_root)
    print(json.dumps({
        "status":summary["status"],
        "qualified_model_leads":summary["qualified_model_leads"],
        "notification_channels":summary["notification_channels"],
        "report":str(path),
    },ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
