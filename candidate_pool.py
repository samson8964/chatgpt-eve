from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

STATE_VERSION = 1
DEFAULT_KEEP_ROUNDS = 8


def _num(value, default=-math.inf):
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _cid(row):
    try:
        return int(row.get("contract_id") or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {"version": STATE_VERSION, "channels": {}}
    try:
        raw = json.loads(path.read_text("utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("state is not an object")
        raw.setdefault("version", STATE_VERSION)
        raw.setdefault("channels", {})
        return raw
    except Exception:
        return {"version": STATE_VERSION, "channels": {}}


def _channel_rounds(path: Path | None, channel: str) -> list[dict]:
    if path is None:
        return []
    rows = _load_state(path).get("channels", {}).get(channel, {}).get("rounds", [])
    return rows if isinstance(rows, list) else []


def _rotation_token() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%d%H") + ("0" if now.minute < 30 else "1")


def _rotation_rank(token: str, cid: int) -> str:
    return hashlib.sha1(f"{token}:{cid}".encode("utf-8")).hexdigest()


def select_candidate_pool(
    rows: Iterable[dict],
    total_limit: int,
    metric_shares: tuple[tuple[str, float], ...],
    *,
    newest_share: float = 0.0,
    exploration_share: float = 0.0,
    diversity_share: float = 0.0,
    product_key: str | None = None,
    newest_key: str = "date_issued",
    fill_metrics: tuple[str, ...] = ("snapshot_profit", "snapshot_roi"),
    state_path: Path | None = None,
    channel: str = "default",
    rotation_token: str | None = None,
) -> tuple[list[dict], dict]:
    """Deterministic exploit/explore pool; protected buckets are never re-sorted away."""
    clean = [dict(r) for r in rows if _cid(r) > 0]
    limit = max(0, int(total_limit))
    if not clean or limit <= 0:
        return [], {"universe":len(clean),"selected":0,"previous_overlap":0.0,"recent_coverage":0.0,"never_recent_selected":0,"by_reason":{}}

    rounds = _channel_rounds(state_path, channel)[-DEFAULT_KEEP_ROUNDS:]
    recent_sets=[]
    for item in rounds:
        try:
            recent_sets.append({int(x) for x in item.get("ids", [])})
        except Exception:
            recent_sets.append(set())
    previous=recent_sets[-1] if recent_sets else set()
    recent_union=set().union(*recent_sets) if recent_sets else set()
    recent_count=Counter(cid for ids in recent_sets for cid in ids)
    last_seen={}
    for idx,ids in enumerate(recent_sets):
        for cid in ids:
            last_seen[cid]=idx

    chosen={}
    reasons={}

    def add_bucket(candidates, quota, label):
        added=0
        for row in candidates:
            if added >= max(0,int(quota)) or len(chosen) >= limit:
                break
            cid=_cid(row)
            if cid <= 0 or cid in chosen:
                continue
            chosen[cid]=dict(row)
            reasons[cid]=label
            added += 1

    for metric,share in metric_shares:
        ranked=sorted(clean,key=lambda r:(_num(r.get(metric)),_num(r.get(fill_metrics[0]) if fill_metrics else 0),-_cid(r)),reverse=True)
        add_bucket(ranked,int(limit*max(0.0,float(share))),f"metric:{metric}")

    newest=sorted(clean,key=lambda r:(str(r.get(newest_key,"")),-_cid(r)),reverse=True)
    add_bucket(newest,int(limit*max(0.0,newest_share)),"newest")

    token=rotation_token or _rotation_token()
    exploration=sorted(clean,key=lambda r:(recent_count.get(_cid(r),0),last_seen.get(_cid(r),-1),_rotation_rank(token,_cid(r))))
    add_bucket(exploration,int(limit*max(0.0,exploration_share)),"exploration")

    if diversity_share > 0 and product_key:
        best={}
        for row in clean:
            product=row.get(product_key)
            if product is None:
                continue
            key=tuple(_num(row.get(m)) for m in fill_metrics)+(-_cid(row),)
            prev=best.get(product)
            if prev is None or key > tuple(_num(prev.get(m)) for m in fill_metrics)+(-_cid(prev),):
                best[product]=row
        diverse=sorted(best.values(),key=lambda r:tuple(_num(r.get(m)) for m in fill_metrics)+(-_cid(r),),reverse=True)
        add_bucket(diverse,int(limit*max(0.0,diversity_share)),"product-diversity")

    fill=sorted(clean,key=lambda r:tuple(_num(r.get(m)) for m in fill_metrics)+(-_cid(r),),reverse=True)
    add_bucket(fill,limit,"economic-fill")

    selected=[]
    for cid,row in chosen.items():
        out=dict(row)
        out["selection_reason"]=reasons.get(cid,"")
        selected.append(out)

    selected_ids={_cid(r) for r in selected}
    current_ids={_cid(r) for r in clean}
    return selected,{
        "universe":len(clean),
        "selected":len(selected),
        "previous_overlap":len(selected_ids & previous)/len(selected_ids) if selected_ids else 0.0,
        "recent_coverage":len(current_ids & recent_union)/len(current_ids) if current_ids else 0.0,
        "never_recent_selected":sum(1 for cid in selected_ids if cid not in recent_union),
        "by_reason":dict(Counter(reasons.get(_cid(r),"") for r in selected)),
        "rotation_token":token,
    }


def record_candidate_pool(path: Path, channel: str, selected_rows: Iterable[dict], *, keep_rounds: int=DEFAULT_KEEP_ROUNDS, at: str|None=None) -> None:
    ids=list(dict.fromkeys(_cid(r) for r in selected_rows if _cid(r)>0))
    state=_load_state(path)
    ch=state.setdefault("channels",{}).setdefault(channel,{})
    rounds=ch.setdefault("rounds",[])
    rounds.append({"at":at or datetime.now(timezone.utc).isoformat(),"ids":ids})
    ch["rounds"]=rounds[-max(1,int(keep_rounds)):]
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(state,ensure_ascii=False,separators=(",",":")),"utf-8")
    tmp.replace(path)
