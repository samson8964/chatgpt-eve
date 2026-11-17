"""Read-only, bounded desktop health view for actual V4 research delivery.

No SQL, network, credentials, scan or maintenance invocation. The two large
reference files are decoded only when their mtime/size changes.
"""
from __future__ import annotations
import gzip
import json
import re
import shutil
from collections import Counter
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path

COMPLETE = "INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED"
RECIPIENTS = {"MikeChong":2124493042, "Arb Hunter":2124830062, "LadyBaBa":2124729692}
WORKER_SENDER = 2124679425
CATEGORIES = ("market", "contract", "blueprint")
RUN = re.compile(r"\d{8}T\d{6}Z-[A-Za-z0-9_-]+")


def _json(path):
    try:
        with path.open(encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def _timestamp(value):
    try:
        t = datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return t if t.tzinfo is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def _receipt_time(value, run):
    t = _timestamp(value)
    try:
        began = datetime.strptime(run[:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return bool(t and t >= began)
    except (ValueError, TypeError):
        return False


def _log_data(text):
    """Only explicit JSON records and allowlisted failure prefixes."""
    recent = {}
    last = {}
    stamp = None
    for line in text.splitlines():
        if line.startswith("START "):
            stamp = line[6:]
            recent = {}
            continue
        for key in ("RESULT","REVIEW_MAIL","GAME_REVIEW_MAIL","ROLLING72_CLEANUP","STORAGE_GOVERNOR"):
            prefix = key+" "
            if line.startswith(prefix):
                try:
                    row = json.loads(line[len(prefix):])
                except ValueError:
                    break
                if isinstance(row,dict):
                    recent[key] = row
                    last[key] = (row,stamp)
                break
        for key in ("REVIEW_MAIL_FAILED","GAME_REVIEW_MAIL_FAILED","RESEARCH_MAIL_SKIPPED"):
            if line.startswith(key+" "):
                recent[key] = True
    return recent,last


def _counts(value):
    if isinstance(value,dict) and set(value)==set(CATEGORIES) and all(
            type(value[k]) is int and 0 <= value[k] <= 10 for k in CATEGORIES):
        return {k:value[k] for k in CATEGORIES}
    return None


def _confirmed_gmail(root,run):
    r = _json(root/"mail-review"/"receipts"/(run+".json"))
    return (r.get("run")==run and r.get("research_only") is True
            and r.get("formal_mail") is False and _receipt_time(r.get("sent_at"),run))


def _confirmed_game(root,run,name,ident):
    if RECIPIENTS.get(name)!=ident:
        return False
    p=root/"mail-review"/"eve-receipts"
    options=[p/(run+"-"+str(ident)+".json")]
    if name=="MikeChong":
        options.append(p/(run+".json"))
    for path in options:
        r=_json(path)
        if (r.get("run")==run and r.get("recipient_id")==ident
                and (r.get("recipient")==name or
                     (name=="MikeChong" and not r.get("recipient")))
                and r.get("research_only") is True and r.get("formal_trade_alert") is False
                and r.get("sender_id")==WORKER_SENDER
                and r.get("source")=="EVE_OFFICIAL_MAIL_VIA_EXISTING_WORKER"
                and _receipt_time(r.get("confirmed_at"),run)
                and ((type(r.get("mail_id")) is int and r["mail_id"]>0)
                     or r.get("already_accepted") is True)):
            return True
    return False


@lru_cache(maxsize=8)
def _reference_summary(path,mtime_ns,size,kind):
    # Cache only small summaries; never keep the full static dictionary.
    try:
        if kind=="names":
            with gzip.open(path,"rt",encoding="utf-8") as f:
                row=json.load(f)
            types,stations=row.get("types"),row.get("stations")
            if row.get("schema")!=1 or not isinstance(types,dict) or not isinstance(stations,dict):
                return {"status":"INVALID"}
            if len(types)<10000 or len(stations)<1000:
                return {"status":"INVALID"}
            return {"status":"INSTALLED","types":len(types),"stations":len(stations),
                    "chinese":sum(isinstance(x,str) and bool(re.search(r"[\u3400-\u9fff]",x))
                                  for x in types.values())}
        row=_json(Path(path))
        if (row.get("schema")!=1 or row.get("region_id")!=10000002
                or row.get("source")!="EVE_REF_ARCHIVE_ESI_FORGE_REGIONAL_DAILY_TRADE_AVERAGE"
                or not isinstance(row.get("quotes"),dict) or not row["quotes"]):
            return {"status":"INVALID"}
        built=date.fromisoformat(row["built_on"])
        latest=date.fromisoformat(row["latest_archive_date"])
        if latest>built or row.get("days_available",0)<=0:
            return {"status":"INVALID"}
        return {"status":"RECORDED","built_on":built.isoformat(),"latest":latest.isoformat(),
                "types":len(row["quotes"])}
    except (OSError,ValueError,TypeError,KeyError,AttributeError,UnicodeError):
        return {"status":"INVALID"}


def _reference(path,kind):
    try:
        s=path.stat()
        out=dict(_reference_summary(str(path),s.st_mtime_ns,s.st_size,kind))
        out["mtime"]=datetime.fromtimestamp(s.st_mtime).strftime("%m-%d %H:%M")
        if kind=="history" and out["status"]=="RECORDED":
            today=datetime.now(timezone.utc).date()
            built=date.fromisoformat(out["built_on"])
            latest=date.fromisoformat(out["latest"])
            out["status"]=("STALE_CACHE" if not 0<=(today-built).days<=3 else
                           "ARCHIVE_LAG" if not 1<=(today-latest).days<=3 else "RECENT")
        return out
    except OSError:
        return {"status":"MISSING"}


def read_health(root,manifest,run,scope_status,task_status,log_text):
    root=Path(root)
    recent,last=_log_data(log_text)
    gmail_cfg=_json(root/"config"/"research_gmail.json")
    game_cfg=_json(root/"config"/"eve_game_mail_review.json")
    gmail_enabled=gmail_cfg.get("enabled") is True
    game_enabled=game_cfg.get("enabled") is True
    config_rows=game_cfg.get("recipients")
    if not isinstance(config_rows,list):
        config_rows=[{"name":game_cfg.get("recipient"),"id":game_cfg.get("recipient_id")}]
    recipients={r["name"]:r.get("id") for r in config_rows if isinstance(r,dict)
                and r.get("name") in RECIPIENTS} if game_enabled else {}
    current=bool(run and RUN.fullmatch(run) and manifest.get("status")=="SHADOW_RECORDED"
                 and task_status not in ("FAILED","SKIPPED_UPSTREAM_STALE","SKIPPED_LOW_DISK"))
    matched=current and recent.get("RESULT",{}).get("run_folder_name")==run
    good=(current and scope_status=="COMPLETE" and manifest.get("coverage_gate")==COMPLETE
          and manifest.get("source_input_integrity")=="ALL_PARSED")
    counts=None
    if good and matched:
        candidates=[_counts(recent.get(k,{}).get("digest_counts"))
                    for k in ("REVIEW_MAIL","GAME_REVIEW_MAIL")
                    if recent.get(k,{}).get("run_folder_name")==run]
        valid=[c for c in candidates if c is not None]
        if valid and all(c==valid[0] for c in valid):
            counts=valid[0]
    def pending_state(channel):
        return ("DISABLED" if not channel else "WAITING" if not current else "UNCONFIRMED")
    gmail=pending_state(gmail_enabled)
    if current and gmail_enabled:
        if _confirmed_gmail(root,run):
            gmail="ACCEPTED"
        elif matched and recent.get("REVIEW_MAIL_FAILED"):
            gmail="FAILED"
    game={name:pending_state(True) for name in recipients}
    if current:
        for name,ident in recipients.items():
            if _confirmed_game(root,run,name,ident):
                game[name]="ACCEPTED"
            elif matched:
                result=recent.get("GAME_REVIEW_MAIL",{})
                details=result.get("recipients") or {}
                item=details.get(name,{}) if isinstance(details,dict) else {}
                if not isinstance(item,dict):
                    item={}
                if (recent.get("GAME_REVIEW_MAIL_FAILED") or
                    (result.get("run_folder_name")==run and
                     (item.get("status")=="V4_GAME_RESEARCH_MAIL_RECIPIENT_FAILED" or
                      (result.get("recipient")==name and
                       result.get("status")=="V4_GAME_RESEARCH_MAIL_RECIPIENT_FAILED")))):
                    game[name]="FAILED"
    codes=Counter()
    if current and isinstance(manifest.get("structure_health"),dict):
        for v in manifest["structure_health"].values():
            if isinstance(v,dict) and v.get("status")!="COMPLETE":
                code=v.get("http_status")
                codes["HTTP "+str(code) if type(code) is int and 100<=code<=599
                      else "采集不完整"]+=1
    roll,roll_at=last.get("ROLLING72_CLEANUP",({},None))
    policy=_json(root/"config"/"rolling72-enabled.json")
    rolling={"configured":policy.get("token")=="V4_ROLLING_72_VERIFIED_EXTERNAL_BACKUP_V1",
             "status":roll.get("status"),"checked_at":roll_at,
             "blocked":roll.get("blocked"),"remaining":roll.get("old_run_count_after"),
             "keep":roll.get("keep_successful_runs",72),
             "reasons":roll.get("blocked_reasons") if isinstance(roll.get("blocked_reasons"),dict) else {}}
    try:
        free=shutil.disk_usage(root).free/(1024**3)
    except OSError:
        free=None
    storage,storage_at=last.get("STORAGE_GOVERNOR",({},None))
    observed=_timestamp(storage_at)
    trend_fresh=bool(observed and 0<=(datetime.now(timezone.utc)-observed).total_seconds()<3*3600)
    severity=("UNKNOWN" if free is None else "STOP" if free<20 else
              "WARNING" if free<40 or (trend_fresh and storage.get("severity") in ("WARNING","STOP"))
              else "OK")
    return {"run":run if current else None,"good":good,"counts":counts,
            "gmail":gmail,"game":game,"game_enabled":game_enabled,
            "station_errors":dict(codes),"rolling":rolling,
            "disk":{"free_gib":free,"severity":severity,
                    "trend_warning":trend_fresh and storage.get("severity")=="WARNING"},
            "names":_reference(root/"reference"/"mail-names.json.gz","names"),
            "history":_reference(root/"reference"/"forge-regional-history-latest.json","history")}


def health_lines(h):
    """Fixed short labels; no secrets, raw error bodies or unverifiable greens."""
    out={}
    counts=h["counts"]
    out["opportunities"]=(("最近捡漏：市场 {market} · 合同 {contract} · 蓝图 {blueprint}".format(**counts),"green")
                          if counts is not None else
                          ("最近捡漏：等待本轮统计（不是零机会）","amber") if h["good"] else
                          ("最近捡漏：本轮数据未完整验证","amber"))
    errors=h["station_errors"]
    out["station_errors"]=(("采集异常："+" / ".join(f"{n}站 {k}" for k,n in errors.items()),"red")
                            if errors else ("采集状态：以上方六站完整性为准","muted"))
    names={"ACCEPTED":"✓","FAILED":"失败","DISABLED":"关闭","WAITING":"等待","UNCONFIRMED":"未确认"}
    channels=[("Gmail",h["gmail"]),*h["game"].items()]
    if not h["game_enabled"]:
        channels.append(("游戏","DISABLED"))
    elif not h["game"]:
        channels.append(("游戏","UNCONFIRMED"))
    values=[v for _,v in channels]
    out["mail"]=("本轮邮件："+" · ".join(f"{k} {names[v]}" for k,v in channels),
                 "red" if "FAILED" in values else "green" if all(v=="ACCEPTED" for v in values) else "amber")
    out["mail_route"]=("游戏收件人："+" + ".join(h["game"]) if h["game"] else "游戏收件人：未配置/关闭",
                       "green" if set(h["game"])=={"MikeChong","Arb Hunter"} else "amber")
    out["mail_note"]=("回执✓＝服务已接受，不代表玩家已读；故障告警也有回执。","muted")
    n=h["names"]
    out["names"]=(f"名称字典：中文 {n['chinese']:,}/{n['types']:,} · {n['mtime']}","green") if n["status"]=="INSTALLED" else ("名称字典：未安装或无效","amber")
    f=h["history"]
    labels={"RECENT":"最新归档","ARCHIVE_LAG":"归档日期滞后","STALE_CACHE":"缓存过期"}
    out["history"]=(f"历史行情：{labels.get(f['status'],'未确认')} {f.get('latest','')}", "green" if f["status"]=="RECENT" else "amber")
    d=h["disk"]
    free=d["free_gib"]
    out["disk"]=("磁盘余量：未知","amber") if free is None else (
        f"磁盘余量：{free:.1f} GiB · "+{"OK":"正常","WARNING":"预警","STOP":"低于20 GiB","UNKNOWN":"未知"}[d["severity"]],
        {"OK":"green","WARNING":"amber","STOP":"red","UNKNOWN":"amber"}[d["severity"]])
    r=h["rolling"]
    if not r["configured"]:
        out["cleanup"]=("历史清理：未启用","muted")
    elif not r["status"]:
        out["cleanup"]=("历史清理：保留72轮 · 等待维护日志","amber")
    else:
        remaining=r["remaining"]
        blocked=r["blocked"]
        out["cleanup"]=(f"清理保留{r['keep']}轮 · 旧轮剩余 {remaining if type(remaining) is int else '--'} · 上次阻塞 {blocked if type(blocked) is int else '--'}",
                         "amber" if blocked or r["status"].startswith("BLOCKED") or type(remaining) is not int or remaining>0 else "green")
    reasons=r["reasons"]
    labels={"GMAIL_UNCONFIRMED":"Gmail回执缺失","GAME_MAIL_UNCONFIRMED:Arb Hunter":"Arb回执缺失",
            "GAME_MAIL_UNCONFIRMED:MikeChong":"Mike回执缺失","GAME_MAIL_UNCONFIRMED:LadyBaBa":"旧角色回执缺失",
            "MAIL_CONFIGURATION_UNKNOWN":"邮件配置未知","UNSAFE_DIRECTORY":"目录保护"}
    shown=[f"{labels.get(k,'其他保护')} {v}" for k,v in sorted(((k,v) for k,v in reasons.items() if type(v) is int and v>0),key=lambda kv:-kv[1])[:2]
           if type(v) is int]
    if shown and r["configured"]:
        out["cleanup_reason"]=("上次阻塞："+" · ".join(shown),"amber")
    elif r["blocked"] or str(r["status"]).startswith("BLOCKED"):
        out["cleanup_reason"]=("上次清理受保护；详细原因待新维护日志","amber")
    else:
        out["cleanup_reason"]=("维护统计仅来自最近一次日志，不触发清理","muted")
    return out
