import datetime as dt
import sys
import tempfile
import json
import time
import os
import subprocess
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app import Monitor, validate_config
from core import (BLUEPRINTS, Planner, historical_reference, extract_blueprints, Store, Client,
                  DEFAULTS, ESI, evaluate, candidate_volume_cap, UncertainSend)
from auth import Auth, protect

def test_planner_50():
    p = Planner()
    needs = p.needs(25308, 50)
    assert needs[40] == 400
    # The planner expands the pure intermediate into its reaction inputs.
    assert needs[25276] == 920

def test_history_weighted_and_stale_guard():
    rows = [{'date': (dt.date.today()-dt.timedelta(days=i+1)).isoformat(), 'average': 10+i, 'volume': 1} for i in range(7)]
    ref = historical_reference(rows, dt.date.today())
    assert ref['volume'] == 7 and ref['price'] == 13
    try:
        historical_reference([{'date': '2020-01-01', 'average': 1, 'volume': 1}], dt.date.today())
    except ValueError as e:
        assert '超过' in str(e)
    else:
        raise AssertionError('stale history should not be accepted')

def test_blueprint_validation_rejects_mixed_and_accepts_real():
    cfg = {'max_contract_isk': 2_000_000_000, 'min_copy_runs': 50, 'jita_only': True,
           'rules': {str(k): {'enabled': True} for k in BLUEPRINTS}}
    base = {'contract_id': 1, 'type': 'item_exchange', 'reward': 0, 'price': 100,
            'start_location_id': 60003760, 'date_issued': '2026-09-08T00:00:00Z',
            'date_expired': '2099-09-08T00:00:00Z'}
    item = {'type_id': 25308, 'quantity': 1, 'runs': 50, 'is_included': True,
            'is_blueprint_copy': True, 'material_efficiency': 0, 'time_efficiency': 0}
    assert extract_blueprints(base, [item], cfg)['runs'] == 50
    assert extract_blueprints(base, [dict(item, is_included=False)], cfg) is None
    assert extract_blueprints(base, [item, dict(item, type_id=25311)], cfg) is None

def test_config_restricts_sender_settings():
    with tempfile.TemporaryDirectory() as d:
        app = Monitor(d)
        cfg = app.store.config()
        cfg2 = validate_config({'client_id': 'abc-123', 'mail_enabled': True}, cfg)
        assert cfg2['recipient_name'] == 'MikeChong' and cfg2['mail_enabled']
        try:
            validate_config({'client_id': 'x;rm'}, cfg)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid client ID should be rejected')
        app.store.close()

def fixture():
    cfg=json.loads(json.dumps(DEFAULTS))
    bp=25308
    c=dict(contract_id=99,type='item_exchange',reward=0,price=200_000_000,
           start_location_id=60003760,date_issued='2026-09-08T00:00:00Z',date_expired='2099-01-01T00:00:00Z')
    items=[dict(type_id=bp,quantity=1,runs=50,is_included=True,is_blueprint_copy=True)]
    p=Planner()
    m=dict(history={str(bp):dict(price=20_000_000,volume=1000,end='2026-09-06')},
           orders={str(mid):[dict(location_id=60003760,is_buy_order=False,price=1000,volume_remain=10_000_000)]
                   for mid in p.needs(bp,50)},blueprint_volumes={str(bp):.01},updated='2026-09-08T00:00:00Z')
    return cfg,c,items,p,m

def test_profit_reserves_full_contract_and_market_depth():
    cfg,c,items,p,m=fixture()
    r=evaluate(c,items,cfg,p,m)
    expected=sum(p.needs(25308,50).values())*1000
    assert r['material']==expected
    assert r['profit']==50*20_000_000*.95-expected-c['price']-10_000_000
    assert r['eligible']
    m['history']['25308']['volume']=30
    r=evaluate(c,items,cfg,p,m)
    assert not r['eligible'] and '成交量' in r['reasons'][0]
    m['orders']['40'][0]['volume_remain']=1
    try: evaluate(c,items,cfg,p,m)
    except ValueError: pass
    else: raise AssertionError('insufficient depth should not be priced')

def test_unknown_bpc_and_requested_goods_never_pass():
    cfg,c,items,p,m=fixture()
    for bad in [dict(items[0],runs=-1),dict(items[0],runs=None),dict(items[0],is_blueprint_copy=None),
                dict(items[0],is_included=False),dict(items[0],quantity=0)]:
        assert extract_blueprints(c,[bad],cfg) is None
    assert extract_blueprints(dict(c,type='auction'),items,cfg) is None
    assert extract_blueprints(c,items+[dict(items[0],type_id=40)],cfg) is None

def test_volume_bound_is_derived_and_unknown_disables_prefilter():
    cfg,c,items,p,m=fixture()
    assert candidate_volume_cap(m,p,cfg)==.05
    m['blueprint_volumes']['25308']=None
    assert candidate_volume_cap(m,p,cfg) is None

def test_http_cache_uses_no_requests_until_expiry_and_304_extends():
    with tempfile.TemporaryDirectory() as d:
        s=Store(d);client=Client(s)
        key=ESI+'/test'
        s.execute('INSERT INTO cache VALUES (?,?,?,?)',(key,'[1]',json.dumps({'etag':'abc','expires':'Wed, 01 Jan 2020 00:00:00 GMT'}),time.time()+300))
        calls=[]
        def request(*a,**kw): calls.append(kw);return 304,{},b''
        client.request=request
        assert client.get('/test')[0]==[1] and not calls
        s.execute('UPDATE cache SET expires=0')
        assert client.get('/test')[0]==[1] and len(calls)==1
        assert client.get('/test')[0]==[1] and len(calls)==1
        assert calls[0]['headers']['If-None-Match']=='abc'
        s.close()

def test_sent_and_uncertain_mail_are_not_resent():
    for uncertain in (False,True):
        with tempfile.TemporaryDirectory() as d:
            a=Monitor(d);cfg,c,items,p,m=fixture();cfg['mail_enabled']=True;a.store.put('config',cfg)
            calls=[]
            class FakeAuth:
                def access(self):return {}
                def recipient(self):return {'id':123}
                def send(self,*args):
                    calls.append(args)
                    if uncertain:raise UncertainSend('uncertain')
                    return 77
            a.auth=FakeAuth()
            row=evaluate(c,items,cfg,p,m)
            a.send_opportunities([row]);a.store.put('next_mail_at',0);a.send_opportunities([row])
            assert len(calls)==1
            assert a.store.rows('SELECT state FROM delivery')[0]['state']==('unknown' if uncertain else 'sent')
            a.store.close()

def test_pause_blocks_mail_and_expired_records_are_inactive():
    with tempfile.TemporaryDirectory() as d:
        a=Monitor(d);cfg,c,items,p,m=fixture();cfg['mail_enabled']=True;a.store.put('config',cfg)
        a.store.put('paused',True)
        a.send_opportunities([evaluate(c,items,cfg,p,m)])
        assert not a.store.rows('SELECT * FROM delivery')
        a.store.close()

def test_dpapi_round_trip_and_wrong_oauth_state():
    raw=b'nonsecret synthetic test value'
    if os.name == 'nt':
        encrypted=protect(raw)
        assert encrypted!=raw and protect(encrypted,True)==raw
    with tempfile.TemporaryDirectory() as d:
        s=Store(d);a=Auth(Client(s),s)
        a.pending=dict(state='correct',expires=time.time()+60)
        try:a.finish('synthetic','incorrect')
        except ValueError:pass
        else:raise AssertionError('wrong state accepted')
        assert not a.file.exists()
        s.close()

def test_relay_rejects_wrong_sender_and_uncertain_post():
    from relay import RelayAuth, SENDER_ID, RECIPIENT_ID
    class FakeClient:
        name='LadyGuaGua'; posts=0; fail=False
        def request(self,url,**kw):
            if url.endswith('/health'):
                return 200,{},f'已授权 · {self.name} ({SENDER_ID})'.encode()
            if url.endswith('/universe/ids'):
                return 200,{},json.dumps({'characters':[{'name':'MikeChong','id':RECIPIENT_ID}]}).encode()
            self.posts+=1
            if self.fail: raise UncertainSend('timeout')
            payload=json.loads(kw['data'])
            assert payload['recipient_id']==RECIPIENT_ID
            assert payload['idempotency_key'].startswith('booster-v1-')
            return 200,{},json.dumps(dict(ok=True,mail_id=42,sender_id=SENDER_ID,recipient_id=RECIPIENT_ID)).encode()
    c=FakeClient();a=RelayAuth(c)
    with patch.dict(os.environ,{'EVE_MAIL_API_KEY':'synthetic-test-key'}):
        c.name='WrongCharacter'
        try: a.send('test','test')
        except ValueError: pass
        else: raise AssertionError('wrong sender accepted')
        assert c.posts==0
        c.name='LadyGuaGua'
        assert a.send('test','test')==42
        c.fail=True
        try: a.send('test','test')
        except UncertainSend: pass
        else: raise AssertionError('uncertain POST accepted')

def test_checkpoint_failure_prevents_mail_post():
    with tempfile.TemporaryDirectory() as d:
        a=Monitor(d);cfg,c,items,p,m=fixture();cfg['mail_enabled']=True;a.store.put('config',cfg)
        class FakeAuth:
            def access(self): return {}
            def recipient(self): return {'id':123}
            def send(self,*args): raise AssertionError('must not send before durable checkpoint')
        a.auth=FakeAuth()
        def checkpoint(): raise RuntimeError('simulated storage failure')
        a.delivery_checkpoint=checkpoint
        try: a.send_opportunities([evaluate(c,items,cfg,p,m)])
        except RuntimeError: pass
        else: raise AssertionError('checkpoint failure ignored')
        a.store.close()

def test_cloud_state_survives_new_runner_and_marks_inflight_unknown():
    from cloud_run import GitState
    original=Path.cwd()
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        subprocess.run(['git','init','--bare',str(root/'remote.git')],check=True,capture_output=True)
        subprocess.run(['git','init',str(root/'checkout')],check=True,capture_output=True)
        try:
            os.chdir(root/'checkout')
            subprocess.run(['git','remote','add','origin',str(root/'remote.git')],check=True,capture_output=True)
            a=Monitor(root/'one');ledger=GitState(a);ledger.load()
            a.store.execute('INSERT INTO delivery VALUES (?,?,?,?,?)',(99,2124493042,'sending','test',time.time()))
            a.store.execute('INSERT INTO inspected VALUES (?,?)',(99,'[]'))
            ledger.save();a.store.close()
            b=Monitor(root/'two');other=GitState(b);other.load()
            assert b.store.rows('SELECT state FROM delivery')[0]['state']=='unknown'
            assert b.store.rows('SELECT id FROM inspected')[0]['id']==99
            other.save();b.store.close()
        finally: os.chdir(original)

if __name__ == '__main__':
    for name in sorted(globals()):
        if name.startswith('test_'):
            globals()[name]()
    print('monitor tests passed')
