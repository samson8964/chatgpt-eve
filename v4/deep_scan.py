"""V4 independent candidate proof demonstrator (SHADOW ONLY).

Every invocation uses the current run's full-universe market/contract snapshots.
All source/type combinations are reconsidered. Only known, authorised locations
can produce a formal candidate; all other potential sources remain RESEARCH.
No mail is sent; output is intended for regression and live-permission auditing.
"""
from __future__ import annotations
import json
import math
import os
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from v4.engine import Order, Policy, contract_proof, market_proof, quarantine_snapshot_candidate, parse_orders_with_quarantine
from v4.catalog import ensure_catalog, blueprint_instance_kind
from v4.sources import market_dataframe, contract_dataframes

JITA = 60003760
KNOWN_STATIONS = {'jita': JITA, 'amarr': 60008494, 'dodixie':60011866}
STRUCTURES = {'four_h':(1053970513596,'main'), 'cj':(1049588174021,'cj'),
              'o4t':(1040804972352,'dc')}
WORKER = 'https://eve-contract-opener.99617224.workers.dev'
ESI = 'https://esi.evetech.net/latest'
UA = 'EVE-V4 shadow verification (github.com/samson8964/chatgpt-eve)'
POLICY = Policy()


def request(url, params=None, headers=None, timeout=50):
    r=requests.get(url,params=params,headers={'User-Agent':UA,**(headers or {})},timeout=timeout)
    r.raise_for_status()
    return r.json(),r.headers


def all_structure_orders(api_key):
    """Fresh all-page reads, no top-N; unsuccessful lane is explicitly FAILED."""
    out,health=[],{}
    for key,(location,profile) in STRUCTURES.items():
        if not api_key:
            health[key]={'status':'FAILED','reason':'missing_api_key'}
            continue
        try:
            first,h=request(WORKER+'/api/structure-market',
                params={'structure_id':location,'auth_profile':profile,'page':1},
                headers={'Authorization':'Bearer '+api_key})
            if not first.get('ok') or int(first.get('structure_id',0)) != location:
                raise ValueError('unverified_structure_response')
            pages=int(first.get('pages') or 1)
            results=list(first.get('orders') or [])
            for page in range(2,pages+1):
                extra,_=request(WORKER+'/api/structure-market',
                    params={'structure_id':location,'auth_profile':profile,'page':page},
                    headers={'Authorization':'Bearer '+api_key})
                if not extra.get('ok') or int(extra.get('page') or 0) != page:
                    raise ValueError('structure_pagination_incomplete')
                results.extend(extra.get('orders') or [])
            out.extend(results)
            health[key]={'status':'COMPLETE','orders':len(results),'pages':pages,'location':location}
        except Exception as exc:
            health[key]={'status':'FAILED','reason':type(exc).__name__+':'+str(exc)[:150]}
    return out,health


def to_orders(rows, *, source):
    # Every raw row is accounted for as a valid order or an explicit proof.
    return parse_orders_with_quarantine(rows, source=source)


def known_station_regions():
    """Region and solar-system returned by public station metadata."""
    output={JITA:{'region':10000002,'system':30000142}}
    for station in (60008494,60011866):
        try:
            s,_=request(ESI+'/universe/stations/%s/'%station)
            system=int(s['system_id'])
            solar,_=request(ESI+'/universe/systems/%s/'%system)
            constellation,_=request(ESI+'/universe/constellations/%s/'%solar['constellation_id'])
            output[station]={'system':system,'region':int(constellation['region_id'])}
        except Exception as exc:
            output[station]={'error':str(exc)[:120]}
    return output


def haul(source,dest,volume,stations):
    if source==dest:
        return 0
    if source in KNOWN_STATIONS.values() and dest in KNOWN_STATIONS.values():
        a,b=stations.get(source,{}),stations.get(dest,{})
        if not a.get('system') or not b.get('system'):
            return None
        try:
            route,_=request(ESI+'/route/%s/%s/'%(a['system'],b['system']),
                params={'flag':'secure','datasource':'tranquility'})
            jumps=max(0,len(route)-1)
            if jumps==0:return None
            return 2_000_000+200*volume*jumps
        except Exception:
            return None
    if source in (x[0] for x in STRUCTURES.values()) or dest in (x[0] for x in STRUCTURES.values()):
        return 10_000_000+500*volume
    return None



def run(market_path,contract_path,output,api_key=''):
    raw_market=market_dataframe(Path(market_path))
    contracts,items=contract_dataframes(Path(contract_path))
    structures,structure_health=all_structure_orders(api_key)
    # Take ALL rows; no previous history/seen/TOP state consulted.
    present={c for c in raw_market.columns}
    needed={'order_id','type_id','location_id','price','volume_remain','is_buy_order'}
    if needed-present: raise RuntimeError('order_fields_missing')
    public_orders,public_rejects=to_orders(raw_market.to_dict('records'),source='PUBLIC')
    authorized_orders,structure_rejects=to_orders(structures,source='STRUCTURE')
    quarantined=public_rejects+structure_rejects
    all_orders=public_orders+authorized_orders
    markets=defaultdict(list)
    for o in all_orders:
        markets[(o.location_id,o.type_id,o.buy)].append(o)
    for (location,typ,buy),book in markets.items():
        book.sort(key=lambda r: (-r.price if buy else r.price, r.order_id))
    approved=set(KNOWN_STATIONS.values())
    approved.update(row['location'] for row in structure_health.values() if row['status']=='COMPLETE')
    # Every executable pair over ALL verified source/destination locations is
    # considered; all other locations were already represented in full census.
    sources=[key for key in markets if not key[2] and key[0] in approved]
    destinations=defaultdict(list)
    for (lid,typ,buy),book in markets.items():
        if buy and lid in approved: destinations[typ].append((lid,book))
    potential_pairs=[]
    for (source,typ,buy) in sources:
        asks=markets[(source,typ,False)]
        for destination,bids in destinations.get(typ,[]):
            if not asks or not bids or source==destination:continue
            if asks[0].price>=bids[0].price:continue
            optimistic=(bids[0].price-asks[0].price)*sum(x.remaining for x in asks)
            if optimistic>=POLICY.profit_floor:
                potential_pairs.append((source,destination,typ))
    # Jita-to-Jita public contracts (least ambiguous, no transport) and
    # approved other station contracts. BPC/manufacturing is NOT implemented.
    cash_contracts=contracts[(contracts['type'].astype(str).str.lower()=='item_exchange')
                             & contracts['start_location_id'].isin(approved)].copy()
    ids=set(t for _,_,t in potential_pairs)
    # Only include included items, not requested barter terms.
    inc=items[items.get('is_included',pd.Series(True,index=items.index)).astype(str).str.lower().isin(['true','1','t'])]
    inc=inc[inc['contract_id'].isin(set(cash_contracts['contract_id'].tolist()))]
    ids.update(int(t) for t in inc['type_id'].dropna().unique())
    catalog=ensure_catalog()
    coverage=catalog.coverage(ids)
    volumes={int(t):catalog.volume(t) for t in ids if catalog.volume(t) is not None}
    missing=coverage['missing_volume']
    stations=known_station_regions()
    proofs=list(quarantined);reasons=defaultdict(int)
    for invalid in quarantined:
        reasons[invalid['reason']]+=1
    for source,dest,typ in potential_pairs:
        unit=volumes.get(int(typ))
        v=unit or 0
        cost=haul(source,dest,v,stations) if unit else None
        proof=market_proof(markets[(source,typ,False)],markets[(dest,typ,True)],
            source_location=source,destination_location=dest,type_id=int(typ),
            volume_m3=unit,haul_isk=cost,policy=POLICY,allowed=True,fresh=True)
        proof.update(volume_m3=unit,haul_isk=cost,source_location=source,destination_location=dest,
                     source_region=stations.get(source,{}).get('region'),
                     destination_region=stations.get(dest,{}).get('region'))
        quarantine_snapshot_candidate(proof)
        proofs.append(proof)
        reasons[proof['reason']]+=1
    # Contract proof only for validated Jita-location item exchange; other
    # station contracts need separate live contract/access transport proof.
    jita_contracts=cash_contracts[cash_contracts['start_location_id']==JITA]
    by_contract=defaultdict(dict)
    bp_states=defaultdict(lambda:defaultdict(int))
    for row in inc[inc['contract_id'].isin(set(jita_contracts['contract_id']))].itertuples(index=False):
        key=int(row.contract_id);typ=int(row.type_id);qty=int(row.quantity)
        if qty>0:by_contract[key][typ]=by_contract[key].get(typ,0)+qty
        if qty>0 and catalog.classification(typ)=='blueprint_type':
            kind=blueprint_instance_kind(getattr(row,'is_blueprint_copy',None),getattr(row,'runs',None))
            bp_states[key][kind]+=qty
    jita_bids={t:book for (location,t,buy),book in markets.items() if location==JITA and buy}
    for row in jita_contracts.to_dict('records'):
        cid=int(row['contract_id'])
        if cid not in by_contract:continue
        if 'date_expired' in row and str(row['date_expired'])[:19] < datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'):
            continue
        # Fail-closed until the complete verified SDE blueprint/item-class
        # dictionary and raw contract item copy metadata are integrated.
        # V4 deliberately does NOT assume blueprint-looking types are BPO.
        classes={int(t):catalog.classification(t) for t in by_contract[cid]}
        proof=contract_proof(row,by_contract[cid],jita_bids,volumes,
            policy=POLICY,haul_isk=0,allowed=True,fresh=True,
            item_classifications=classes)
        proof.update(included_items=by_contract[cid],
                     contract_blueprint_evidence=dict(bp_states[cid]),
                     included_volumes={str(i):volumes.get(i) for i in by_contract[cid]},
                     source_location=JITA,destination_location=JITA,region_id=10000002,
                     expires_at=str(row.get('date_expired','')))
        quarantine_snapshot_candidate(proof)
        proofs.append(proof)
        reasons[proof['reason']]+=1
    report=dict(status='SHADOW_ONLY_NO_LIVE_ALERTS',run_id='v4-'+uuid.uuid4().hex,
       market_orders=len(all_orders),public_market_orders=len(public_orders),
       authorized_structure_orders=len(authorized_orders),
       rejected_input_orders=len(quarantined),
       invalid_public_orders=len(public_rejects),
       invalid_structure_orders=len(structure_rejects),
       source_input_integrity=('PARTIAL_QUARANTINED' if quarantined else 'ALL_PARSED'),
       source_locations_total=len({o.location_id for o in all_orders}),
       source_types_total=len({o.type_id for o in all_orders}),contract_rows=len(contracts),
       structure_health=structure_health,metadata_missing=missing,metadata_requested=len(ids),
       catalog_meta=catalog.meta,catalog_coverage=coverage,
       verified_approved_locations=len(approved),market_potential_pairs=len(potential_pairs),
       contract_cash_known_location=len(cash_contracts),contract_jita_examined=len(jita_contracts),
       contract_blueprint_states={state:sum(states.get(state,0) for states in bp_states.values())
                                  for state in ('BPC','BPO','UNKNOWN_BLUEPRINT')},
       proof_count=len(proofs),model_candidates=sum(x.get('model_candidate') is True for x in proofs),
       formal_candidates=sum(x.get('status')=='MAIL' for x in proofs),
       reason_counts=dict(reasons),candidate_preview=[p for p in proofs if p.get('status')=='MAIL'][:10],
       warnings=['All snapshot-derived model candidates downgraded to WATCH: no live ESI order verification',
                 'Full-universe public contracts/markets census succeeded separately',
                 'Non-verified destination routes and BPC are not production mail-eligible',
                 'All contract cash liquidations held RESEARCH until verified BPO/BPC and regular-item metadata is integrated'] +
                 (['Malformed input orders were explicitly quarantined; this is PARTIAL source input coverage']
                  if quarantined else []))
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str,allow_nan=False),encoding='utf-8')
    proof_path=path.with_name('all_proofs.jsonl')
    with proof_path.open('w',encoding='utf-8') as fh:
        for row in proofs:
            fh.write(json.dumps(row,ensure_ascii=False,default=str,separators=(',',':'),allow_nan=False)+'\n')
    return report


def main():
    from argparse import ArgumentParser
    p=ArgumentParser()
    p.add_argument('--market',default='/tmp/v4-market/market_orders.csv.bz2')
    p.add_argument('--contracts',default='/tmp/v4-market/public_contracts.tar.bz2')
    p.add_argument('--output',default='v4_output/latest/deep_shadow.json')
    args=p.parse_args()
    result=run(args.market,args.contracts,args.output,os.getenv('EVE_MARKET_API_KEY',''))
    print(json.dumps({k:v for k,v in result.items() if k!='candidate_preview'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
