"""Read-only V4 market gap attribution: optimistic global -> Jita depth -> mail.

Forensic only. Reads saved market archive and market proofs, never network,
mail, scheduler, first-seen index, databases or scan state.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from v4.engine import Order, Policy
from v4.market_execution import gross_depth_upper_bound
from v4.npc_station_catalog import load_catalog
from v4.source_freshness_audit import latest_run
from v4.station_funnel_audit import gates
from v4.sources import market_dataframe

JITA=60003760
AMARR=60008494
DODIXIE=60011866
STRUCTURES=(1053970513596,1049588174021,1040804972352)
PUBLIC_APPROVED=(AMARR,DODIXIE)
FLOOR=Policy().profit_floor


def global_candidates(raw: pd.DataFrame):
    """Exactly the same optimistic formula and input validity as full_scan.py."""
    df=raw[["location_id","type_id","is_buy_order","price","volume_remain"]].copy()
    for col in ("price","volume_remain"):
        df[col]=pd.to_numeric(df[col],errors="coerce")
    df["volume_remain"]=df["volume_remain"].fillna(0)
    for col in ("location_id","type_id"):
        df[col]=pd.to_numeric(df[col],errors="coerce").fillna(0).astype("int64")
    flag=df["is_buy_order"]
    buy=(flag if flag.dtype==bool else
         flag.fillna(False).astype(str).str.lower().isin(("true","1","t")))
    good=(df["price"]>0)&df["price"].notna()&(df["volume_remain"]>0)&(
        df["type_id"]>0)&(df["location_id"]>0)
    asks=df[good & ~buy].groupby(["location_id","type_id"],sort=False).agg(
        min_ask=("price","min"),total_sell=("volume_remain","sum")
    ).reset_index()
    best=df[good & buy].groupby("type_id",sort=False).agg(
        max_bid=("price","max")
    ).reset_index()
    possible=asks.merge(best,on="type_id",how="left",validate="many_to_one")
    gross=(possible["max_bid"]-possible["min_ask"]).clip(lower=0)*possible["total_sell"]
    return possible.loc[gross>=FLOOR,["location_id","type_id"]].copy()


def _make_order(row, is_buy):
    return Order(order_id=int(row.order_id),
                 type_id=int(row.type_id),
                 location_id=int(row.location_id),
                 buy=is_buy,price=float(row.price),
                 remaining=int(row.volume_remain))


def _groups(rows:pd.DataFrame, *, is_buy:bool):
    result=defaultdict(list)
    if rows.empty:
        return result
    for row in rows[["order_id","type_id","location_id","price","volume_remain"]].itertuples(index=False):
        if int(row.volume_remain)<=0 or float(row.price)<=0:
            continue
        result[(int(row.location_id),int(row.type_id))].append(_make_order(row,is_buy))
    for book in result.values():
        book.sort(key=lambda x:(-x.price if is_buy else x.price, x.order_id))
    return result


def global_to_jita_attribution(market:pd.DataFrame, candidates:pd.DataFrame, npc_catalog=None):
    """Check all optimistic public candidates with *actual Jita depth*.

    Site scope, remote bid vs Jita quote, and insufficient Jita book depth are
    mutually exclusive primary reasons. Scanned private structures are
    separately reported from deep-run proofs, never included here.
    """
    ckeys=set((int(lid),int(typ)) for lid,typ in candidates.itertuples(index=False,name=None))
    types={typ for _,typ in ckeys}
    core=market[["order_id","location_id","type_id","is_buy_order","price","volume_remain"]].copy()
    for col in ("order_id","location_id","type_id","volume_remain"):
        core[col]=pd.to_numeric(core[col],errors="coerce")
    core["price"]=pd.to_numeric(core["price"],errors="coerce")
    isbuy=(core["is_buy_order"] if core["is_buy_order"].dtype==bool
           else core["is_buy_order"].astype(str).str.lower().isin(("true","1","t")))
    usable=core["price"].gt(0)&core["volume_remain"].gt(0)&core["type_id"].gt(0)&core["location_id"].gt(0)
    jita_rows=core.loc[usable&isbuy&core["location_id"].eq(JITA)&core["type_id"].isin(types)]
    bids=_groups(jita_rows,is_buy=True)
    # Inner join with 3721 candidate keys, avoiding millions of unused asks.
    eligible_asks=core.loc[usable&~isbuy, ["order_id","location_id","type_id","price","volume_remain"]]
    cand_rows=candidates[["location_id","type_id"]].drop_duplicates()
    only_candidate_asks=eligible_asks.merge(cand_rows,on=["location_id","type_id"],
                                            how="inner",validate="many_to_one")
    asks=_groups(only_candidate_asks,is_buy=False)
    byreason=Counter()
    examples=defaultdict(list)
    jita_gross_pass=[]
    for loc,typ in sorted(ckeys):
        if loc==JITA:
            reason="JITA_AS_SOURCE_NOT_A_CROSS_STATION_TRADE"
        elif not bids.get((JITA,typ)):
            reason="NO_JITA_BUY"
        else:
            book=asks.get((loc,typ),[])
            if not book:
                raise RuntimeError("CANDIDATE_ASK_BOOK_MISSING")
            jb=bids[(JITA,typ)]
            if book[0].price>=jb[0].price:
                reason="JITA_BEST_BID_NOT_ABOVE_SOURCE_ASK"
            elif gross_depth_upper_bound(book,jb)<FLOOR:
                reason="JITA_MATCHED_GROSS_BELOW_50M"
            else:
                reason="JITA_MATCHED_GROSS_AT_LEAST_50M"
        byreason[reason]+=1
        if len(examples[reason])<6:
            examples[reason].append({"location_id":loc,"type_id":typ})
        if reason=="JITA_MATCHED_GROSS_AT_LEAST_50M":
            jita_gross_pass.append((loc,typ))
    approved=[x for x in jita_gross_pass if x[0] in PUBLIC_APPROVED]
    other=[x for x in jita_gross_pass if x[0] not in PUBLIC_APPROVED]
    stations=((npc_catalog or {}).get("stations") or {})
    outside_categories=Counter()
    outside_station=Counter()
    for location,typ in other:
        station=stations.get(str(location)) or {}
        band=station.get("band")
        outside_categories[band if band in ("HIGH","LOW") else "NOT_CONFIRMED_HIGH_LOW_NPC"]+=1
        outside_station[location]+=1
    return {
        "global_optimistic_public_pairs":len(ckeys),
        "global_candidate_explained_by_jita_exit":dict(byreason),
        "jita_depth_gross_at_least_50m_any_public_source":len(jita_gross_pass),
        "jita_depth_gross_at_least_50m_public_approved_sources":len(approved),
        "jita_depth_gross_at_least_50m_public_unapproved_sources":len(other),
        "unapproved_gross_candidates_by_npc_security":dict(outside_categories),
        "unapproved_gross_candidates_top_source_stations":[
            {"location_id":loc,"candidate_types":n}
            for loc,n in outside_station.most_common(10)
        ],
        "reason_examples":dict(examples),
        "warning":"Unapproved Jita-depth-positive pairs are NOT verified net-profit opportunities; tax, freight, access, ROI and stress are still unknown."
    }


def _mail_safety_match(row):
    if not (row.get("model_candidate") is True and row.get("quantity_optimized") is True
            and row.get("valuation_location_id")==JITA
            and row.get("destination_location")==JITA
            and row.get("valuation_basis")=="JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE"):
        return False
    try:
        qty=int(row.get("quantity"))
        net=float(row.get("profit"))
        roi=float(row.get("roi"))
        stress=float(row.get("stress_profit"))
        cost=float(row.get("cost"))
        sell_vwap=float(row.get("source_vwap_isk_per_unit"))
        buy_vwap=float(row.get("jita_vwap_isk_per_unit"))
        paid=float(row.get("executed_sell_cost"))
        gross=float(row.get("executed_jita_buy_gross"))
        source=int(row.get("source_location"))
    except (TypeError,ValueError,OverflowError):
        return False
    return (source!=JITA and source>0 and qty>0 and
            all(math.isfinite(v) for v in (net,roi,stress,cost,sell_vwap,buy_vwap,paid,gross))
            and net>0 and roi>0 and stress>FLOOR and cost>0
            and sell_vwap>0 and buy_vwap>0
            and math.isclose(qty*sell_vwap,paid,rel_tol=1e-9)
            and math.isclose(qty*buy_vwap,gross,rel_tol=1e-9))


def deep_to_mail(folder:Path, deep:dict):
    reasons=Counter()
    fail=Counter()
    origins=Counter()
    eligible=0
    proofs=0
    models=0
    sample=[]
    with (folder/"all_proofs.jsonl").open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            p=json.loads(line)
            if p.get("kind")!="market":
                continue
            proofs+=1
            reasons[str(p.get("reason") or "UNKNOWN")]+=1
            if p.get("model_candidate") is True:
                models+=1
            else:
                gate_labels=gates(p)
                fail.update(gate_labels)
                if len(sample)<10 and p.get("reason")=="BELOW_GATE_OR_STRESS":
                    sample.append({
                        "source_location":p.get("source_location"),
                        "type_id":p.get("type_id"),
                        "profit":p.get("profit"),
                        "roi":p.get("roi"),
                        "stress_profit":p.get("stress_profit"),
                        "failed_gates":gate_labels
                    })
            if _mail_safety_match(p):
                eligible+=1
                origins[str(p.get("source_location"))]+=1
    return {
        "market_deep_proofs":proofs,
        "expected_deep_proofs":deep.get("market_proofs_examined"),
        "deep_proof_count_matches":proofs==int(deep.get("market_proofs_examined",-1)),
        "model_candidates":models,
        "eligible_market_research_leads_before_display_cap":eligible,
        "market_email_display_cap":10,
        "maximum_market_leads_shown_in_email":min(10,eligible),
        "eligible_leads_by_source_location":dict(origins),
        "market_proof_reasons":dict(reasons),
        "failed_economic_gates_multi_label_overlaps":dict(fail),
        "near_miss_examples":sample,
        "note":"One rejected proof can fail multiple gates; failure counts do not sum to rejected total. Historical first-seen ordering is NOT de-duplication or another economic gate."
    }


def audit(folder:Path, root:Path):
    full=json.loads((folder/"full_market_report.json").read_text("utf-8"))
    deep=json.loads((folder/"deep_shadow.json").read_text("utf-8"))
    source=folder/"source"/"market_orders.csv.bz2"
    df=market_dataframe(source)
    cand=global_candidates(df)
    actual=int((full.get("market") or {}).get("optimistic_initial_candidates",-1))
    if len(cand)!=actual:
        raise RuntimeError(f"GLOBAL_PREFILTER_MISMATCH:{len(cand)}!={actual}")
    npc=load_catalog(root)
    before=global_to_jita_attribution(df,cand,npc)
    after=deep_to_mail(folder,deep)
    stored=deep.get("market_station_sell_census") or {}
    structures=sum(int((stored.get(name) or {}).get("sell_types_optimistic_gate_passed") or 0)
                   for name in ("4-H","C-J","O4T"))
    public_deep=int(deep.get("market_potential_pairs") or 0)-structures
    before["authorized_structure_jita_gross_pairs"]=structures
    before["public_approved_gross_pairs_expected_from_deep"]=public_deep
    before["public_approved_gross_pairs_reconcile"]=(
        before["jita_depth_gross_at_least_50m_public_approved_sources"]==public_deep)
    before["total_jita_gross_pairs_reconcile"]=(
        (before["jita_depth_gross_at_least_50m_public_approved_sources"]+structures)
        ==int(deep.get("market_potential_pairs") or -1))
    return {
        "run":folder.name,
        "basis":"SAME_RUN_ARCHIVED_MARKET_ORDERS_AND_DEEP_PROOFS",
        "global_to_jita":before,
        "deep_to_mail":after,
        "live_execution_verified":False,
        "read_only":True
    }


def main():
    ap=argparse.ArgumentParser(description="Explain public global -> approved Jita depth -> research email market losses")
    ap.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    ap.add_argument("--run",type=str,default=None,
                    help="Previously completed run folder name, e.g. 20261016T122301Z-44ce82b9")
    ap.add_argument("--output",type=Path,default=None)
    opts=ap.parse_args()
    if opts.run:
        if not opts.run.replace("-","").isalnum() or "/" in opts.run or "\\" in opts.run:
            ap.error("RUN_NAME_INVALID")
        folder=opts.data_root/"runs"/opts.run
        if not folder.is_dir():
            ap.error("RUN_NOT_FOUND")
        manifest=json.loads((folder/"manifest.json").read_text("utf-8"))
        if manifest.get("status")!="SHADOW_RECORDED":
            ap.error("RUN_NOT_COMPLETED")
    else:
        folder,_=latest_run(opts.data_root)
    result=audit(folder,opts.data_root)
    if opts.output:
        opts.output.parent.mkdir(parents=True,exist_ok=True)
        opts.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
        "run":result["run"],
        "global_to_jita":{k:v for k,v in result["global_to_jita"].items()
                          if k not in ("reason_examples","unapproved_gross_candidates_top_source_stations")},
        "deep_to_mail":{k:v for k,v in result["deep_to_mail"].items()
                        if k not in ("near_miss_examples",)},
        "detail_report_file":str(opts.output) if opts.output else None
    },ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
