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

from v4.engine import Order, Policy, contract_proof, market_proof
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


def to_orders(rows):
    result=[]
    for raw in rows:
        try:
            result.append(Order.parse(raw))
        except (ValueError,KeyError,TypeError,OverflowError):
            pass
    return result


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


def metadata(type_ids):
    volumes={}; missing=0
    def volume_of(tid):
        d,_=request('https://ref-data.everef.net/types/%s'%tid,timeout=35)
        raw=d.get('packaged_volume',d.get('volume'))
        v=float(raw)
        return (tid,v) if math.isfinite(v) and v>0 else (tid,None)
    with ThreadPoolExecutor(max_workers=10) as pool:
        tasks={pool.submit(volume_of,int(t)):int(t) for t in type_ids}
        for future in as_completed(tasks):
            tid=tasks[future]
            try: _,v=future.result()
            except Exception: v=None
            if v:volumes[tid]=v
            else:missing+=1
    return volumes,missing


def run(market_path,contract_path,output,api_key=''):
    raw_market=market_dataframe(Path(market_path))
    contracts,items=contract_dataframes(Path(contract_path))
    structures,structure_health=all_structure_orders(api_key)
    # Take ALL rows; no previous history/seen/TOP state consulted.
    present={c for c in raw_market.columns}
    needed={'order_id','type_id','location_id','price','volume_remain','is_buy_order'}
    if needed-present: raise RuntimeError('order_fields_missing')
    all_orders=to_orders(raw_market.to_dict('records'))
    all_orders+=to_orders(structures)
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
    volumes,missing=metadata(ids)
    stations=known_station_regions()
    proofs=[];reasons=defaultdict(int)
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
        proofs.append(proof)
        reasons[proof['reason']]+=1
    # Contract proof only for validated Jita-location item exchange; other
    # station contracts need separate live contract/access transport proof.
    jita_contracts=cash_contracts[cash_contracts['start_location_id']==JITA]
    by_contract=defaultdict(dict)
    for row in inc[inc['contract_id'].isin(set(jita_contracts['contract_id']))].itertuples(index=False):
        key=int(row.contract_id);typ=int(row.type_id);qty=int(row.quantity)
        if qty>0:by_contract[key][typ]=by_contract[key].get(typ,0)+qty
    jita_bids={t:book for (location,t,buy),book in markets.items() if location==JITA and buy}
    for row in jita_contracts.to_dict('records'):
        cid=int(row['contract_id'])
        if cid not in by_contract:continue
        if 'date_expired' in row and str(row['date_expired'])[:19] < datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'):
            continue
        proof=contract_proof(row,by_contract[cid],jita_bids,volumes,
            policy=POLICY,haul_isk=0,allowed=True,fresh=True)
        proof.update(included_items=by_contract[cid],
                     included_volumes={str(i):volumes.get(i) for i in by_contract[cid]},
                     source_location=JITA,destination_location=JITA,region_id=10000002,
                     expires_at=str(row.get('date_expired','')))
        proofs.append(proof)
        reasons[proof['reason']]+=1
    report=dict(status='SHADOW_ONLY_NO_LIVE_ALERTS',run_id='v4-'+uuid.uuid4().hex,
       market_orders=len(all_orders),source_locations_total=len({o.location_id for o in all_orders}),
       source_types_total=len({o.type_id for o in all_orders}),contract_rows=len(contracts),
       structure_health=structure_health,metadata_missing=missing,metadata_requested=len(ids),
       verified_approved_locations=len(approved),market_potential_pairs=len(potential_pairs),
       contract_cash_known_location=len(cash_contracts),contract_jita_examined=len(jita_contracts),
       proof_count=len(proofs),formal_candidates=sum(x.get('status')=='MAIL' for x in proofs),
       reason_counts=dict(reasons),candidate_preview=[p for p in proofs if p.get('status')=='MAIL'][:10],
       warnings=['Snapshot execution proof is NOT equivalent to latest live ESI validation',
                 'Full-universe public contracts/markets census succeeded separately',
                 'Non-verified destination routes and BPC are not production mail-eligible'])
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    proof_path=path.with_name('all_proofs.jsonl')
    with proof_path.open('w',encoding='utf-8') as fh:
        for row in proofs:
            fh.write(json.dumps(row,ensure_ascii=False,default=str,separators=(',',':'))+'\n')
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
