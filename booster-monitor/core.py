"""ESI public data, conservative manufacturing estimates and persistent alert state."""
import concurrent.futures as futures
import datetime as dt
import email.utils
import json
import math
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
ESI = 'https://esi.evetech.net'
VERSION = '1.3.0'
# ESI validates against UTC-11. Pin the reviewed, fully elapsed day.
DATE = '2026-09-07'
REGION = 10000002
JITA = 60003760
BLUEPRINTS = {25308: '蓝色药丸', 25311: '撞击感', 25322: '疯癫', 25329: '坠落感',
              25511: '思维冲击', 25512: '梦呓', 25513: 'X—本能', 25539: '游离感'}
DEFAULTS = dict(recipient_name='MikeChong', recipient_id=None, client_id='', mail_enabled=False,
                max_contract_isk=2_000_000_000, min_copy_runs=50, jita_only=False,
                sale_fee=0.05, reserve_per_50=10_000_000, max_week_share=0.25,
                rules={str(k): dict(enabled=True, min_profit_50=100_000_000, min_roi=0.20)
                       for k in BLUEPRINTS})

def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def stamp(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()

class ApiError(Exception):
    def __init__(self, status, message='接口暂不可用', retry=60):
        super().__init__(message)
        self.status, self.retry = status, retry

class UncertainSend(Exception):
    pass

class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.directory / 'monitor.sqlite', check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, body TEXT, headers TEXT, expires REAL);
        CREATE TABLE IF NOT EXISTS alerts (contract_id INTEGER PRIMARY KEY, payload TEXT, updated REAL);
        CREATE TABLE IF NOT EXISTS delivery (contract_id INTEGER, recipient INTEGER, state TEXT,
          detail TEXT, updated REAL, PRIMARY KEY(contract_id,recipient));
        ''')
        # A crash after POST might have sent the mail. Never resend such attempts automatically.
        self.execute("UPDATE delivery SET state='unknown',detail='程序中断，投递结果待核对' WHERE state='sending'")

    def execute(self, sql, args=()):
        with self.lock:
            c = self.db.execute(sql, args)
            self.db.commit()
            return c

    def rows(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def get(self, key, default=None):
        r = self.rows('SELECT value FROM kv WHERE key=?', (key,))
        return json.loads(r[0]['value']) if r else default

    def put(self, key, value):
        self.execute('INSERT OR REPLACE INTO kv VALUES (?,?)', (key, json.dumps(value, ensure_ascii=False)))

    def close(self):
        with self.lock:
            self.db.close()

    def config(self):
        return self.get('config', json.loads(json.dumps(DEFAULTS)))

class Client:
    def __init__(self, store):
        self.store = store
        self.gate = threading.Lock()
        self.next_request = 0
        self.blocked_until = 0

    def request(self, url, method='GET', data=None, headers=None):
        with self.gate:
            now = time.time()
            if now < self.blocked_until:
                raise ApiError(429, '接口要求暂缓请求', math.ceil(self.blocked_until-now))
            delay = max(0, self.next_request-now)
            if delay:
                time.sleep(delay)
            self.next_request = time.time() + .2
        h = {'User-Agent': f'BoosterBlueprintMonitor/{VERSION} (eve:MikeChong)',
             'X-Compatibility-Date': DATE, 'X-Tenant': 'tranquility'}
        h.update(headers or {})
        req = urllib.request.Request(url, method=method, data=data, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                return response.status, dict(response.headers.items()), response.read()
        except urllib.error.HTTPError as e:
            hdr = dict(e.headers.items())
            if e.code == 304:
                return 304, hdr, b''
            low = {k.lower(): v for k, v in hdr.items()}
            retry = 60
            value = low.get('retry-after', low.get('x-esi-error-limit-reset', '60'))
            try:
                retry = max(1, int(value))
            except ValueError:
                try:
                    retry = max(1, int(email.utils.parsedate_to_datetime(value).timestamp()-time.time()))
                except (ValueError, TypeError):
                    pass
            if e.code in (420, 429, 503):
                self.blocked_until = time.time() + retry
            if method == 'POST' and '/mail' in url and e.code >= 500:
                raise UncertainSend('邮件请求返回服务器错误，需核对是否已投递') from None
            raise ApiError(e.code, f'接口返回 {e.code}', retry) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            if method == 'POST' and '/mail' in url:
                raise UncertainSend('邮件请求连接中断，需核对是否已投递') from None
            raise ApiError(0, '网络连接失败，稍后重试') from None

    def get(self, path, ttl=300):
        key = ESI + path
        saved = self.store.rows('SELECT * FROM cache WHERE key=?', (key,))
        saved = saved[0] if saved else None
        if saved and saved['expires'] > time.time():
            return json.loads(saved['body']), json.loads(saved['headers'])
        old_h = json.loads(saved['headers']) if saved else {}
        h = {'If-None-Match': old_h['etag']} if old_h.get('etag') else {}
        status, received, raw = self.request(key, headers=h)
        received = {k.lower(): v for k, v in received.items()}
        if int(received.get('x-esi-error-limit-remain', '100')) < 10:
            self.blocked_until = time.time() + int(received.get('x-esi-error-limit-reset', '60'))
        if status == 204:
            raise ApiError(204, '合同已经过期或被接受')
        response_expires = received.get('expires')
        if status == 304:
            if not saved:
                raise ApiError(304, '缓存缺失')
            body = saved['body']
            old_h.update(received)
            received = old_h
        else:
            body = raw.decode('utf-8')
            json.loads(body)
        expires = time.time() + ttl
        try:
            expires = email.utils.parsedate_to_datetime(response_expires).timestamp()
        except (KeyError, ValueError, TypeError, AttributeError):
            pass
        self.store.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?,?)',
                           (key, body, json.dumps(received), max(time.time()+1, expires)))
        return json.loads(body), received

    def pages(self, path, ttl):
        sep = '&' if '?' in path else '?'
        first, h = self.get(path + sep + 'page=1', ttl)
        last_modified = h.get('last-modified')
        result = list(first)
        for page in range(2, int(h.get('x-pages', '1'))+1):
            part, ph = self.get(path + sep + f'page={page}', ttl)
            if last_modified and ph.get('last-modified') != last_modified:
                raise ApiError(0, '分页数据更新时间不一致，等待下次完整快照', 60)
            result.extend(part)
        return result

class Planner:
    def __init__(self, file=BASE/'recipes.json'):
        self.recipes = json.loads(Path(file).read_text(encoding='utf-8'))
        self.by_id = {r['id']: r for r in self.recipes}
        self.by_product = {r['products'][0]['id']: r for r in self.recipes}
        self.names = {m['id']: m['name'] for r in self.recipes for m in r['materials']+r['products']}
        self.ordered = sorted(self.recipes, key=lambda r: self.depth(r['products'][0]['id']), reverse=True)

    def depth(self, item):
        r = self.by_product.get(item)
        return 0 if not r else 1+max(self.depth(m['id']) for m in r['materials'])

    def needs(self, bp, runs):
        product = self.by_id[bp]['products'][0]
        demand = {product['id']: runs*product['quantity']}
        for r in self.ordered:
            p = r['products'][0]
            wanted = demand.pop(p['id'], 0)
            if wanted:
                batches = math.ceil(wanted/p['quantity'])
                for m in r['materials']:
                    demand[m['id']] = demand.get(m['id'], 0)+batches*m['quantity']
        return demand

def purchase_cost(orders, quantity):
    cost = 0
    for o in sorted((o for o in orders if o['location_id'] == JITA and not o['is_buy_order']), key=lambda o: o['price']):
        n = min(quantity, o['volume_remain'])
        cost += n*o['price']
        quantity -= n
        if quantity == 0:
            return cost
    raise ValueError('吉他卖单数量不足，不能给出完整采购成本')

def historical_reference(history, today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    valid = [d for d in history if dt.date.fromisoformat(d['date']) < today]
    if not valid:
        raise ValueError('缺少完整交易日数据')
    end = max(dt.date.fromisoformat(d['date']) for d in valid)
    if (today-end).days > 3:
        raise ValueError('成交历史已超过 3 天，暂停利润提醒')
    week = [d for d in valid if 0 <= (end-dt.date.fromisoformat(d['date'])).days < 7]
    volume = sum(d['volume'] for d in week)
    if not volume:
        raise ValueError('最近七天没有成品成交')
    return dict(price=sum(d['average']*d['volume'] for d in week)/volume,
                volume=volume, end=end.isoformat(), start=(end-dt.timedelta(days=6)).isoformat())

def extract_blueprints(contract, items, cfg):
    """Reject buy requests, auctions, mixed bundles and unverified BPC run counts."""
    if contract.get('type') != 'item_exchange' or contract.get('reward', 0) != 0:
        return None
    price = contract.get('price')
    if not isinstance(price, (int, float)) or not math.isfinite(price) or price < 0 or price > cfg['max_contract_isk']:
        return None
    if cfg['jita_only'] and contract.get('start_location_id') != JITA:
        return None
    if stamp(contract['date_expired']) <= time.time() or not items:
        return None
    bp = items[0]['type_id']
    if bp not in BLUEPRINTS or not cfg['rules'][str(bp)]['enabled']:
        return None
    for item in items:
        if (item.get('is_included') is not True or item.get('type_id') != bp
            or item.get('is_blueprint_copy') is not True
            or type(item.get('runs')) is not int or item['runs'] < cfg['min_copy_runs']
            or type(item.get('quantity')) is not int or item['quantity'] < 1):
            return None
    return dict(bp=bp, runs=sum(i['runs']*i['quantity'] for i in items),
                copies=sum(i['quantity'] for i in items), price=price)

def evaluate(contract, items, cfg, planner, markets):
    info = extract_blueprints(contract, items, cfg)
    if not info:
        return None
    bp, runs = info['bp'], info['runs']
    ref = markets['history'][str(bp)]
    costs = {mid: purchase_cost(markets['orders'][str(mid)], q) for mid, q in planner.needs(bp, runs).items()}
    material = sum(costs.values())
    reserve = cfg['reserve_per_50']*runs/50
    quantity = planner.by_id[bp]['products'][0]['quantity']*runs
    net_revenue = quantity*ref['price']*(1-cfg['sale_fee'])
    spend = material+info['price']+reserve
    profit = net_revenue-spend
    profit50 = profit*50/runs
    roi = profit/spend if spend else 0
    rule = cfg['rules'][str(bp)]
    share = quantity/ref['volume']
    reasons = []
    if profit50 < rule['min_profit_50']:
        reasons.append('每 50 流程利润未达门槛')
    if roi < rule['min_roi']:
        reasons.append('投入回报率未达门槛')
    if share > cfg['max_week_share']:
        reasons.append('本批产量占一周市场成交量过高')
    return dict(**info, contract_id=contract['contract_id'], name=BLUEPRINTS[bp],
                material=material, reserve=reserve, profit=profit, profit50=profit50, roi=roi,
                week_volume=ref['volume'], week_share=share, reference_price=ref['price'],
                history_end=ref['end'], eligible=not reasons, reasons=reasons,
                location_id=contract['start_location_id'], expired=contract['date_expired'],
                issued=contract['date_issued'], discovered=utc(), price_updated=markets['updated'],
                region_id=contract.get('region_id'),
                blueprints=[dict(runs=i['runs'], quantity=i['quantity'], me=i.get('material_efficiency'),
                                 te=i.get('time_efficiency')) for i in items])

def refresh_markets(client, planner, cfg):
    ids = set()
    active = [bp for bp in BLUEPRINTS if cfg['rules'][str(bp)]['enabled']]
    for bp in active:
        ids.update(planner.needs(bp, 50))
    out = dict(orders={}, history={}, blueprint_volumes={}, updated=utc(), errors={})
    def order(mid):
        return client.pages(f'/markets/{REGION}/orders?order_type=sell&type_id={mid}', 300)
    with futures.ThreadPoolExecutor(max_workers=4) as pool:
        pending = {pool.submit(order, mid): mid for mid in ids}
        for f in futures.as_completed(pending):
            mid = pending[f]
            out['orders'][str(mid)] = f.result()
    for bp in active:
        pid = planner.by_id[bp]['products'][0]['id']
        blueprint_type, _ = client.get(f'/universe/types/{bp}', 86400)
        out['blueprint_volumes'][str(bp)] = blueprint_type.get('volume')
        try:
            history, _ = client.get(f'/markets/{REGION}/history?type_id={pid}', 3600)
            out['history'][str(bp)] = historical_reference(history)
        except ValueError as e:
            out['errors'][str(bp)] = str(e)
    return out

def candidate_volume_cap(markets, planner, cfg):
    """A pure BPC bundle larger than this cannot satisfy the batch liquidity rule."""
    caps = []
    for bp in BLUEPRINTS:
        if not cfg['rules'][str(bp)]['enabled'] or str(bp) not in markets['history']:
            continue
        volume = markets.get('blueprint_volumes', {}).get(str(bp))
        if not isinstance(volume, (int, float)) or volume <= 0:
            return None  # Unknown official volume: do not guess a cutoff.
        output = planner.by_id[bp]['products'][0]['quantity']
        copies = math.floor(markets['history'][str(bp)]['volume']*cfg['max_week_share']/(cfg['min_copy_runs']*output))
        caps.append(copies*volume)
    return max(caps, default=0)
