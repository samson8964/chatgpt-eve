"""V4 shadow-only bulk ingestion to new durable actor.

Refuses to operate if release mode is enabled. No mail privileges/side effects.
"""
from __future__ import annotations
import json
import os
import requests
from pathlib import Path

BASE = 'https://eve-v4-opportunity-store.99617224.workers.dev'


def upload(report_path: str, proof_path: str, api_key: str) -> dict:
    if not api_key:
        raise RuntimeError('V4 store API key missing')
    h={'Authorization':'Bearer '+api_key,'Content-Type':'application/json'}
    health=requests.get(BASE+'/health',timeout=15).json()
    if not health.get('ok') or health.get('dispatch_enabled'):
        raise RuntimeError('Shadow ingestion refused: V4 store not DISABLED/healthy')
    report=json.loads(Path(report_path).read_text('utf-8'))
    if report.get('status') != 'SHADOW_ONLY_NO_LIVE_ALERTS':
        raise RuntimeError('Not a verified V4 shadow report')
    run_id=report['run_id']
    response=requests.post(BASE+'/api/v4/run',headers=h,json={
        'run_id':run_id,'outcome':'SHADOW',
        'coverage':{k:v for k,v in report.items() if k in
            ('contract_rows','market_orders','market_potential_pairs',
             'verified_approved_locations','proof_count','formal_candidates','structure_health')}},
        timeout=40)
    response.raise_for_status()
    response=response.json()
    if not response.get('ok'): raise RuntimeError('V4 store run ack failed')
    count=0;pending_added=0;batches=0
    def send(rows):
        nonlocal count,pending_added,batches
        if not rows:return
        r=requests.post(BASE+'/api/v4/record',headers=h,json={
            'run_id':run_id, 'proofs':rows,'recipients':['MikeChong','LadyBaBa']},
            timeout=100)
        r.raise_for_status()
        data=r.json()
        if not data.get('ok') or data.get('dispatch_enabled') or data.get('pending_added'):
            raise RuntimeError('Shadow sent to active outbox or store rejected: '+repr(data))
        count+=int(data['committed']);batches+=1
    batch=[]
    for line in Path(proof_path).open(encoding='utf-8'):
        if not line.strip():continue
        proof=json.loads(line)
        if proof.get('instance') and proof.get('status') in ('MAIL','WATCH'):
            batch.append(proof)
        if len(batch)>=200:
            send(batch);batch=[]
    send(batch)
    return {'ok':True,'run_id':run_id,'stored':count,'batches':batches,'new_emails':0}


def main():
    api_key=os.getenv('EVE_MARKET_API_KEY','')
    result=upload('v4_output/latest/deep_shadow.json','v4_output/latest/all_proofs.jsonl',api_key)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
