"""V4 independent candidate proof demonstrator (SHADOW ONLY).

Every invocation uses the current run's full-universe market/contract snapshots.
All source/type combinations are reconsidered. Only known, authorised locations
can produce a formal candidate; all other potential sources remain RESEARCH.
No mail is sent; output is intended for regression and live-permission auditing.
"""
from __future__ import annotations
import json
import math
import hashlib
import os
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import pandas as pd
import requests

from v4.engine import Order, Policy, contract_proof, market_proof, profitable_trade, quarantine_snapshot_candidate, parse_orders_with_quarantine
from v4.catalog import ensure_catalog, blueprint_instance_kind
from v4.market_depth import top_price_levels, station_sell_census
from v4.market_execution import gross_depth_upper_bound
from v4.sources import market_dataframe, contract_dataframes
from v4.npc_station_catalog import load_catalog

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
    """Fresh complete private-market pagination with bounded page-level retries."""
    from v4.structure_transport import all_structure_orders as fetch_all
    return fetch_all(api_key, structures=STRUCTURES, worker=WORKER, fetch=request)

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


@lru_cache(maxsize=32)
def _secure_route_jumps(source_system, dest_system):
    """Cache ESI secure-route hop count once per station pair per process.

    A failed route lookup stays unverified for this scan, not free transport.
    """
    try:
        route,_=request(ESI+'/route/%s/%s/'%(source_system,dest_system),
            params={'flag':'secure','datasource':'tranquility'})
        jumps=max(0,len(route)-1)
        return jumps if jumps>0 else None
    except Exception:
        return None


def haul(source,dest,volume,stations,npc_stations=None):
    """Research-only transport estimate, never a verified route quotation."""
    if source==dest:
        return 0
    if source in KNOWN_STATIONS.values() and dest in KNOWN_STATIONS.values():
        a,b=stations.get(source,{}),stations.get(dest,{})
        if not a.get('system') or not b.get('system'):
            return None
        jumps=_secure_route_jumps(int(a['system']),int(b['system']))
        return 2_000_000+200*volume*jumps if jumps is not None else None
    if dest==JITA and npc_stations and source in npc_stations:
        band=npc_stations[source].get('band')
        if band=='HIGH':
            return 15_000_000+750*volume
        if band=='LOW':
            # Lowsec hauling risk buffer: safe route/transport not verified.
            return 50_000_000+2500*volume
        return None
    if source in (x[0] for x in STRUCTURES.values()) or dest in (x[0] for x in STRUCTURES.values()):
        return 10_000_000+500*volume
    return None



def run(market_path,contract_path,output,api_key=''):
    # CCP SDE installed once in EVE-V4-Data/reference. Never fetched hourly.
    target=Path(output).resolve()
    data_root=(target.parent.parent.parent if target.parent.parent.name=='runs'
               else target.parent)
    npc_reference=load_catalog(data_root)
    npc_stations=({int(k):v for k,v in npc_reference['stations'].items()}
                  if npc_reference else {})
    raw_market=market_dataframe(Path(market_path))
    contracts,items=contract_dataframes(Path(contract_path))
    structures,structure_health=all_structure_orders(api_key)
    # Take ALL rows; no previous history/seen/TOP state consulted.
    present={c for c in raw_market.columns}
    needed={'order_id','type_id','location_id','price','volume_remain','is_buy_order'}
    if needed-present: raise RuntimeError('order_fields_missing')
    public_orders,public_inactive=to_orders(raw_market.to_dict('records'),source='PUBLIC')
    authorized_orders,structure_inactive=to_orders(structures,source='STRUCTURE')
    # Every snapshot row is either an actionable order, an audited non-actionable
    # zero-remaining order, or an invalid quarantined input.
    zero_public=[row for row in public_inactive if row['reason']=='SOURCE_ORDER_ZERO_REMAINING']
    zero_structure=[row for row in structure_inactive if row['reason']=='SOURCE_ORDER_ZERO_REMAINING']
    public_rejects=[row for row in public_inactive if row['reason']=='SOURCE_ORDER_INVALID']
    structure_rejects=[row for row in structure_inactive if row['reason']=='SOURCE_ORDER_INVALID']
    quarantined=public_rejects+structure_rejects
    non_actionable=zero_public+zero_structure
    if len(public_orders)+len(public_inactive)!=len(raw_market) or (
            len(authorized_orders)+len(structure_inactive)!=len(structures)):
        raise RuntimeError('SOURCE_ORDER_ACCOUNTING_MISMATCH')
    all_orders=public_orders+authorized_orders
    # Hash each complete private ESI structure book without persisting
    # individual order details. Stable ordering makes cross-run equality
    # meaningful. A SHA match means the tracked active book did not change.
    # This telemetry is informational, not a trade/live freshness gate.
    private_market_hashes={}
    for name,(station_id,_) in STRUCTURES.items():
        if (structure_health.get(name) or {}).get('status') != 'COMPLETE':
            private_market_hashes[name]=None
            continue
        rows=sorted((o for o in authorized_orders if o.location_id==station_id),
                    key=lambda o:o.order_id)
        fields=[(o.order_id,o.type_id,o.buy,o.price,o.remaining,
                 o.minimum,o.range) for o in rows]
        private_market_hashes[name]=hashlib.sha256(
            json.dumps(fields,separators=(',',':')).encode('utf-8')).hexdigest()
    markets=defaultdict(list)
    for o in all_orders:
        markets[(o.location_id,o.type_id,o.buy)].append(o)
    for (location,typ,buy),book in markets.items():
        book.sort(key=lambda r: (-r.price if buy else r.price, r.order_id))
    approved=set(KNOWN_STATIONS.values())
    approved.update(row['location'] for row in structure_health.values() if row['status']=='COMPLETE')
    # All approved private-station sell types are counted and benchmarked.
    # This census includes even products excluded by the profit prefilter.
    station_census = station_sell_census(
        markets, locations={'4-H': STRUCTURES['four_h'][0],
                            'C-J': STRUCTURES['cj'][0],
                            'O4T': STRUCTURES['o4t'][0]},
        jita=JITA, floor=POLICY.profit_floor)
    # Market cash exit is ALWAYS the Jita 4-4 station's BUY depth, just
    # like contracts; do not value any item at remote stations' local bids.
    # Full raw market inputs remain audited in this run.
    sources=[key for key in markets if not key[2] and key[0] in approved
             and key[0] != JITA]
    potential_pairs=[]
    for (source,typ,buy) in sources:
        asks=markets[(source,typ,False)]
        bids=markets.get((JITA,typ,True),[])
        if not asks or not bids or asks[0].price>=bids[0].price:
            continue
        # Use matched Jita BUY liquidity on the other side, never local bids.
        # This is a safe ceiling: fees, haul and min-volume can only LOWER it.
        if gross_depth_upper_bound(asks,bids)>=POLICY.profit_floor:
            potential_pairs.append((source,JITA,typ))
    # Expand CONTRACT source scope only. Keep MARKET approval unchanged.
    # NPC high/low security verified by CCP SDE, never ID-range guesses.
    approved_contracts=approved | set(npc_stations)
    cash_contracts=contracts[(contracts['type'].astype(str).str.lower()=='item_exchange')
                             & contracts['start_location_id'].isin(approved_contracts)].copy()
    ids=set(t for _,_,t in potential_pairs)
    # EVE item-exchange contracts can also REQUEST additional items. Treating
    # only the included side as a cash-only purchase would invent profit.
    # Any requested, ambiguous, or missing inclusion flag fails closed.
    if 'is_included' not in items.columns:
        raise RuntimeError('CONTRACT_ITEM_INCLUSION_FLAG_MISSING')
    included_flags=items['is_included'].astype(str).str.lower().isin(['true','1','t'])
    requested_ids=set(items.loc[~included_flags, 'contract_id'].dropna().tolist())
    requested_contracts_excluded=int(cash_contracts['contract_id'].isin(requested_ids).sum())
    cash_contracts=cash_contracts[~cash_contracts['contract_id'].isin(requested_ids)].copy()
    # Additional term-sensitive cost models belong in a separate barter engine.
    inc=items.loc[included_flags].copy()
    inc=inc[inc['contract_id'].isin(set(cash_contracts['contract_id'].tolist()))]
    ids.update(int(t) for t in inc['type_id'].dropna().unique())
    catalog=ensure_catalog()
    coverage=catalog.coverage(ids)
    volumes={int(t):catalog.volume(t) for t in ids if catalog.volume(t) is not None}
    missing=coverage['missing_volume']
    stations=known_station_regions()
    proofs=list(quarantined)+list(non_actionable);reasons=defaultdict(int)
    for invalid in proofs:
        reasons[invalid['reason']]+=1
    for source,dest,typ in potential_pairs:
        unit=volumes.get(int(typ))
        asks=markets[(source,typ,False)]
        jita_bids=markets[(JITA,typ,True)]
        # Price every candidate lot with its OWN total cargo volume.
        # Avoid optimizing on a fixed transport charge for the full book.
        haul_for_units=(lambda n,src=source,v=unit:
                        haul(src,JITA,float(v)*n,stations) if v else None)
        proof=market_proof(asks,jita_bids,
            source_location=source,destination_location=JITA,type_id=int(typ),
            volume_m3=unit,haul_isk=None,haul_for_units=haul_for_units,
            policy=POLICY,allowed=True,fresh=True)
        selected=proof.get('quantity') or 0
        cargo_m3=(float(unit)*selected if unit and selected else None)
        proof.update(volume_m3=unit,cargo_volume_m3=cargo_m3,
                     haul_isk=proof.get('haul'),
                     source_top5_sell=top_price_levels(asks,buy=False),
                     jita_top5_buy=top_price_levels(jita_bids,buy=True),
                     valuation_location_id=JITA,
                     valuation_basis='JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE',
                     source_location=source,destination_location=JITA,
                     source_region=stations.get(source,{}).get('region'),
                     destination_region=stations.get(JITA,{}).get('region'))
        quarantine_snapshot_candidate(proof)
        proofs.append(proof)
        reasons[proof['reason']]+=1
    # User-approved fixed valuation benchmark: Jita IV - Moon 4 - Caldari
    # Navy Assembly Plant (60003760), its real BUY ORDER DEPTH only.
    # Contract location is a source/pickup point; haul must be charged for
    # non-Jita contracts, never silently treated as zero or as Jita inventory.
    # This is snapshot RESEARCH, never a live executable contract assertion.
    local_contracts=cash_contracts
    jita_contract_count=int((local_contracts['start_location_id']==JITA).sum())
    by_contract=defaultdict(dict)
    bp_states=defaultdict(lambda:defaultdict(int))
    for row in inc[inc['contract_id'].isin(set(local_contracts['contract_id']))].itertuples(index=False):
        key=int(row.contract_id);typ=int(row.type_id);qty=int(row.quantity)
        if qty>0:by_contract[key][typ]=by_contract[key].get(typ,0)+qty
        if qty>0 and catalog.classification(typ)=='blueprint_type':
            kind=blueprint_instance_kind(getattr(row,'is_blueprint_copy',None),getattr(row,'runs',None))
            bp_states[key][kind]+=qty
    for row in local_contracts.to_dict('records'):
        cid=int(row['contract_id'])
        if cid not in by_contract:continue
        if 'date_expired' in row and str(row['date_expired'])[:19] < datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'):
            continue
        # Fail-closed until the complete verified SDE blueprint/item-class
        # dictionary and raw contract item copy metadata are integrated.
        # V4 deliberately does NOT assume blueprint-looking types are BPO.
        classes={int(t):catalog.classification(t) for t in by_contract[cid]}
        contract_location=int(row['start_location_id'])
        jita_bids={t:markets.get((JITA,int(t),True),[])
                   for t in by_contract[cid]}
        item_volumes=[volumes.get(int(t)) for t in by_contract[cid]]
        volume_m3=(sum(float(volumes[int(t)])*int(qty)
                       for t,qty in by_contract[cid].items())
                   if all(v is not None and math.isfinite(v) and v>0
                          for v in item_volumes) else None)
        haul_estimate=(haul(contract_location,JITA,volume_m3,stations,npc_stations)
                       if volume_m3 is not None else None)
        proof=contract_proof(row,by_contract[cid],jita_bids,volumes,
            policy=POLICY,haul_isk=haul_estimate,allowed=True,fresh=True,
            item_classifications=classes)
        proof.update(included_items=by_contract[cid],
                     contract_price=float(row.get('price') or 0),
                     contract_title=str(row.get('title') or '')[:180],
                     valuation_basis='JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE',
                     valuation_location_id=JITA,
                     contract_access_verified=False,
                     haul_cost_estimate_isk=haul_estimate,
                     haul_route_verified=False,
                     volume_m3=volume_m3,
                     requested_items_present=False,
                     contract_blueprint_evidence=dict(bp_states[cid]),
                     included_volumes={str(i):volumes.get(i) for i in by_contract[cid]},
                     source_location=contract_location,
                     source_security=(npc_stations.get(contract_location) or {}).get('security'),
                     source_security_band=(npc_stations.get(contract_location) or {}).get('band'),
                     source_station_name=(npc_stations.get(contract_location) or {}).get('name'),
                     haul_model=('NPC_HIGHSEC_CONSERVATIVE_UNVERIFIED'
                                 if (npc_stations.get(contract_location) or {}).get('band')=='HIGH'
                                 and contract_location not in KNOWN_STATIONS.values() else
                                 'NPC_LOWSEC_RISK_BUFFER_UNVERIFIED'
                                 if (npc_stations.get(contract_location) or {}).get('band')=='LOW'
                                 else 'LEGACY_STATION_OR_STRUCTURE_ESTIMATE'),
                     destination_location=JITA,
                     jita_exit_buy_orders_only=True,
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
       zero_remaining_public_orders=len(zero_public),
       zero_remaining_structure_orders=len(zero_structure),
       non_actionable_zero_remaining_orders=len(non_actionable),
       public_market_rows_raw=len(raw_market),
       structure_market_rows_raw=len(structures),
       source_input_integrity=('PARTIAL_QUARANTINED' if quarantined else 'ALL_PARSED'),
       source_locations_total=len({o.location_id for o in all_orders}),
       source_types_total=len({o.type_id for o in all_orders}),contract_rows=len(contracts),
       structure_health=structure_health,
       private_market_order_book_sha256=private_market_hashes,
       metadata_missing=missing,metadata_requested=len(ids),
       catalog_meta=catalog.meta,catalog_coverage=coverage,
       verified_approved_locations=len(approved),market_potential_pairs=len(potential_pairs),
       market_pricing_basis='JITA_4_4_BUY_DEPTH_SNAPSHOT',
       market_prefilter_basis='TWO_SIDED_MATCHED_DEPTH_GROSS_MARGIN_BEFORE_FEES',
       market_execution_basis='OPTIMIZED_MATCHED_QUANTITY_AND_VWAP',
       market_station_sell_census=station_census,
       market_top5_price_definition='UNWEIGHTED_MEAN_OF_DISTINCT_PRICE_LEVELS',
       market_proofs_examined=sum(p.get('kind')=='market' for p in proofs),
       contract_cash_known_location=len(cash_contracts),
       contract_requested_items_excluded=requested_contracts_excluded,
       contract_jita_examined=jita_contract_count,
       contract_approved_locations_examined=len(local_contracts),
       npc_catalog_status=('INSTALLED_SDE_FULL_NPC_HIGH_LOW'
                           if npc_reference else 'NOT_INSTALLED_LEGACY_CONTRACT_SCOPE'),
       npc_catalog_sde_version=(npc_reference or {}).get('sde_version'),
       npc_catalog_highsec_stations=(npc_reference or {}).get('highsec_stations'),
       npc_catalog_lowsec_stations=(npc_reference or {}).get('lowsec_stations'),
       npc_contracts_approved_for_deep_analysis=int(
           local_contracts['start_location_id'].isin(set(npc_stations)).sum()),
       npc_contract_scope_definition='CCP_SDE_NPC_STATIONS_WITH_POSITIVE_SYSTEM_SECURITY',
       contract_pricing_basis='JITA_4_4_BUY_DEPTH_SNAPSHOT',
       contract_blueprint_states={state:sum(states.get(state,0) for states in bp_states.values())
                                  for state in ('BPC','BPO','UNKNOWN_BLUEPRINT')},
       proof_count=len(proofs),model_candidates=sum(x.get('model_candidate') is True for x in proofs),
       formal_candidates=sum(x.get('status')=='MAIL' for x in proofs),
       reason_counts=dict(reasons),candidate_preview=[p for p in proofs if p.get('status')=='MAIL'][:10],
       warnings=([] if npc_reference else
                 ['NPC SDE catalog not installed; contract coverage is LEGACY ONLY'])
                + ['All snapshot-derived model candidates downgraded to WATCH: no live ESI order verification',
                 'Full-universe public contracts/markets census succeeded separately',
                 'Non-verified destination routes and BPC are not production mail-eligible',
                 'ALL contract item valuations use Jita 4-4 BUY order-depth snapshots regardless of pickup location',
                 'Non-Jita estimated haul is deducted when calculable, otherwise HAUL_UNVERIFIED; no live delivery/access verification'] +
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
