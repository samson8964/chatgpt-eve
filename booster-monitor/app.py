import argparse
import concurrent.futures as futures
from collections import defaultdict, deque
import json
import math
import os
import secrets
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from core import (ApiError, BASE, BLUEPRINTS, Client, DEFAULTS, JITA, Planner, REGION,
                  Store, UncertainSend, candidate_volume_cap, evaluate, refresh_markets, stamp, utc, VERSION)
from auth import Auth, CALLBACK, RECIPIENT, SENDER, digest
from snapshot_hints import refresh_hints

def validate_config(data, current):
    cfg = json.loads(json.dumps(current))
    limits = dict(max_contract_isk=(1, 1e12), min_copy_runs=(1, 100000), sale_fee=(0, .5),
                  reserve_per_50=(0, 1e11), max_week_share=(.01, 10))
    for key, (lo, hi) in limits.items():
        val = data.get(key, cfg[key])
        if type(val) not in (int, float) or not math.isfinite(val) or not lo <= val <= hi:
            raise ValueError(f'{key} 的数值超出范围')
        if key == 'min_copy_runs' and int(val) != val:
            raise ValueError('流程数必须是整数')
        cfg[key] = val
    for key in ('jita_only', 'mail_enabled'):
        if key in data:
            if type(data[key]) is not bool:
                raise ValueError('开关值无效')
            cfg[key] = data[key]
    cid = str(data.get('client_id', cfg['client_id'])).strip()
    if len(cid) > 150 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in cid):
        raise ValueError('Client ID 格式无效')
    cfg['client_id'] = cid
    for bp in BLUEPRINTS:
        rule = data.get('rules', {}).get(str(bp), cfg['rules'][str(bp)])
        if type(rule.get('enabled')) is not bool:
            raise ValueError('品种开关无效')
        for key, lo, hi in [('min_profit_50', 0, 1e12), ('min_roi', 0, 100)]:
            x = rule.get(key)
            if type(x) not in (int, float) or not math.isfinite(x) or not lo <= x <= hi:
                raise ValueError('利润门槛无效')
        cfg['rules'][str(bp)] = {k: rule[k] for k in ('enabled', 'min_profit_50', 'min_roi')}
    cfg['recipient_name'] = RECIPIENT
    return cfg

class Monitor:
    def __init__(self, directory):
        self.store = Store(directory)
        self.client = Client(self.store)
        self.planner = Planner()
        self.auth = Auth(self.client, self.store)
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.scan_lock = threading.Lock()
        self.mail_lock = threading.Lock()
        self.csrf = secrets.token_urlsafe(32)
        self.markets = None
        self.price_signature = None
        self.delivery_checkpoint = None
        self.market_at = 0
        self.active_ids = set()
        self.verified_ids = set()
        self.hint_loader = lambda: refresh_hints(self.store, BLUEPRINTS)
        self.priority_ids = set()
        self.state = dict(stage='准备启动', running=False, scanned=0, candidates=0,
                          last_scan=None, next_scan=None, market_updated=None, error=None, mail_error=None)
        self.store.execute('CREATE TABLE IF NOT EXISTS inspected (id INTEGER PRIMARY KEY, items TEXT)')

    def public_contracts(self, cfg):
        regions = [REGION] if cfg['jita_only'] else self.client.get('/universe/regions', 86400)[0]
        contracts = {}
        errors = {}
        self.state.update(regions_total=len(regions), regions_checked=0, region_errors={})
        def fetch(region):
            return self.client.pages(f'/contracts/public/{region}', 1800)
        with futures.ThreadPoolExecutor(max_workers=4) as pool:
            tasks = {pool.submit(fetch, region): region for region in regions}
            for task in futures.as_completed(tasks):
                region = tasks[task]
                try:
                    for row in task.result():
                        contracts[row['contract_id']] = dict(row, region_id=region)
                except ApiError as e:
                    errors[str(region)] = dict(status=e.status, message=str(e))
                self.state['regions_checked'] += 1
                self.state['region_errors'] = dict(errors)
        self.state['coverage_complete'] = not errors
        if not contracts and errors:
            raise ApiError(0, '本轮星域合同列表读取失败，未完成核验')
        return list(contracts.values())

    def next_candidates(self, candidates, inspected, limit):
        # Snapshot item types are hints only. Actual items always come from ESI.
        ordered = sorted(candidates, key=lambda c: c['date_issued'], reverse=True)
        priority = [c for c in ordered if c['contract_id'] not in inspected
                    and c['contract_id'] in self.priority_ids][:limit]
        selected_ids = {c['contract_id'] for c in priority}
        buckets = defaultdict(deque)
        for c in ordered:
            if c['contract_id'] not in inspected and c['contract_id'] not in selected_ids:
                buckets[c.get('region_id', REGION)].append(c)
        regions = sorted(buckets)
        cursor = self.store.get('region_cursor', 0)
        regions = [r for r in regions if r > cursor]+[r for r in regions if r <= cursor]
        queue = deque(regions)
        chosen = priority
        while queue and len(chosen) < limit:
            region = queue.popleft()
            chosen.append(buckets[region].popleft())
            if buckets[region]:
                queue.append(region)
        return chosen

    def status(self):
        entries = self.store.rows('SELECT payload FROM alerts ORDER BY updated DESC')
        rows = [json.loads(x['payload']) for x in entries]
        for r in rows:
            r['active'] = (r['contract_id'] in self.active_ids and r['contract_id'] in self.verified_ids
                and stamp(r['expired']) > time.time() and not self.state.get('error'))
        rows.sort(key=lambda r: (r['active'], r['eligible'], r['profit50']), reverse=True)
        return dict(version=VERSION, state=dict(self.state), config=self.store.config(),
                    blueprints=BLUEPRINTS, auth=self.auth.public(), rows=rows[:200],
                    recipient=self.store.get('recipient'), csrf=self.csrf, pid=os.getpid(),
                    delivery=self.store.rows('SELECT * FROM delivery ORDER BY updated DESC LIMIT 100'))

    def scan(self, limit=160):
        if not self.scan_lock.acquire(blocking=False):
            return
        try:
            self.state.update(running=True, stage='读取各星域公开合同', error=None, new_inspected=0)
            cfg = self.store.config()
            contracts = self.public_contracts(cfg)
            self.active_ids = {c['contract_id'] for c in contracts}
            candidates = [c for c in contracts if c.get('type') == 'item_exchange'
                and 0 <= c.get('price', -1) <= cfg['max_contract_isk'] and not c.get('reward', 0)
                and (not cfg['jita_only'] or c.get('start_location_id') == JITA)
                and stamp(c['date_expired']) > time.time()]
            candidates.sort(key=lambda c: c['date_issued'], reverse=True)
            signature = json.dumps(cfg['rules'], sort_keys=True)
            if not self.markets or time.time()-self.market_at > 1800 or self.price_signature != signature:
                self.state['stage'] = '更新吉他材料价格与成品成交参考价'
                self.markets = refresh_markets(self.client, self.planner, cfg)
                self.market_at = time.time()
                self.price_signature = signature
                self.state['market_updated'] = self.markets['updated']
            self.state['market_errors'] = self.markets.get('errors', {})
            self.state['before_volume_filter'] = len(candidates)
            cap = candidate_volume_cap(self.markets, self.planner, cfg)
            if cap is not None:
                candidates = [c for c in candidates if c.get('volume') is None or c['volume'] <= cap+1e-7]
            self.state['volume_cap'] = cap
            unavailable = self.store.get('unavailable_until', {})
            inspected = {r['id']: json.loads(r['items']) for r in self.store.rows('SELECT * FROM inspected')}
            inspected = {cid: items for cid, items in inspected.items()
                         if items or unavailable.get(str(cid), 0) > time.time()}
            self.state['stage'] = '从公开快照定位目标蓝图'
            hints = self.hint_loader()
            self.priority_ids = {int(cid) for cid in hints.get('contracts', {})}
            self.state.update(snapshot_modified=hints.get('modified'), snapshot_error=hints.get('error'),
                              snapshot_target_contracts=len(self.priority_ids))
            unknown = self.next_candidates(candidates, inspected, limit)
            self.state.update(stage='核验蓝图物品和剩余流程', candidates=len(candidates),
                              scanned=sum(c['contract_id'] in inspected for c in candidates))
            def inspect(c):
                try:
                    return c['contract_id'], self.client.pages(f"/contracts/public/items/{c['contract_id']}", 3600)
                except ApiError as e:
                    if e.status in (204, 403, 404):
                        return c['contract_id'], []
                    raise
            self.state.update(item_errors=0, item_error=None)
            with futures.ThreadPoolExecutor(max_workers=4) as pool:
                pending = [pool.submit(inspect, c) for c in unknown]
                for f in futures.as_completed(pending):
                    if f.cancelled():
                        continue
                    try:
                        cid, items = f.result()
                    except ApiError as e:
                        self.state['item_errors'] += 1
                        self.state['item_error'] = str(e)
                        if e.status in (420, 429, 503) or self.state['item_errors'] >= 5:
                            for other in pending:
                                other.cancel()
                        continue
                    inspected[cid] = items
                    self.store.execute('INSERT OR REPLACE INTO inspected VALUES (?,?)', (cid, json.dumps(items)))
                    if items:
                        unavailable.pop(str(cid), None)
                    else:
                        unavailable[str(cid)] = time.time()+1800
                    self.state['scanned'] += 1
                    self.state['new_inspected'] += 1
            self.store.put('unavailable_until', {cid: until for cid, until in unavailable.items()
                                                if until > time.time()})
            if unknown:
                self.store.put('region_cursor', unknown[-1].get('region_id', REGION))
            current = []
            verified = set()
            for c in candidates:
                if self.stop.is_set() or self.store.get('paused', False):
                    break
                cid = c['contract_id']
                if cid not in inspected:
                    continue
                try:
                    result = evaluate(c, inspected[cid], cfg, self.planner, self.markets)
                except (ValueError, KeyError):
                    # Unknown/stale price data must never become an opportunity.
                    continue
                if result:
                    verified.add(cid)
                    self.store.execute('INSERT OR REPLACE INTO alerts VALUES (?,?,?)',
                                       (cid, json.dumps(result, ensure_ascii=False), time.time()))
                    if result['eligible']:
                        current.append(result)
            self.verified_ids = verified
            self.state.update(stage='等待下一次检查', last_scan=utc(), opportunities=len(current),
                              pending=len(candidates)-self.state['scanned'])
            if cfg == self.store.config() and not self.store.get('paused', False) and cfg['mail_enabled']:
                self.send_opportunities(current)
        finally:
            self.state['running'] = False
            self.scan_lock.release()

    def send_opportunities(self, current):
        with self.mail_lock:
            if self.store.get('paused', False) or not self.store.config()['mail_enabled']:
                return
            self.state['mail_error'] = None
            if not current:
                return
            if time.time() < self.store.get('next_mail_at', 0):
                return
            try:
                self.auth.access()
                rid = self.auth.recipient()['id']
            except (ValueError, ApiError, RuntimeError) as e:
                self.state['mail_error'] = str(e)
                return
            done = {r['contract_id'] for r in self.store.rows(
                "SELECT contract_id FROM delivery WHERE recipient=? AND state IN ('sent','sending','unknown','error')", (rid,))}
            rows = sorted((r for r in current if r['contract_id'] not in done), key=lambda r: r['profit50'], reverse=True)[:10]
            if not rows:
                return
            for r in rows:
                self.store.execute('INSERT OR REPLACE INTO delivery VALUES (?,?,?,?,?)',
                    (r['contract_id'], rid, 'sending', '正在发送', time.time()))
            if self.delivery_checkpoint:
                # A durable cloud ledger must be saved before any mail POST.
                self.delivery_checkpoint()
            try:
                mid = self.auth.send(*digest(rows))
                status, detail = 'sent', f'游戏邮件编号 {mid}'
                self.store.put('next_mail_at', time.time()+1800)
            except UncertainSend as e:
                status, detail = 'unknown', str(e)
            except ApiError as e:
                status, detail = ('pending' if e.status in (420, 429) else 'error'), str(e)
                self.store.put('next_mail_at', time.time()+max(60, e.retry))
            except Exception:
                # Includes malformed response after a successful POST: do not duplicate it.
                status, detail = 'unknown', '投递结果未确认，请在游戏中核对'
            for r in rows:
                self.store.execute('UPDATE delivery SET state=?,detail=?,updated=? WHERE contract_id=? AND recipient=?',
                                   (status, detail, time.time(), r['contract_id'], rid))
            if status != 'sent':
                self.state['mail_error'] = detail
            if self.delivery_checkpoint:
                self.delivery_checkpoint()

    def run(self):
        while not self.stop.is_set():
            delay = 30
            if self.store.get('paused', False):
                self.state['stage'] = '已暂停'
            else:
                try:
                    self.scan()
                except ApiError as e:
                    self.state.update(error=str(e), stage='接口暂不可用，等待重试')
                    delay = max(60, e.retry)
                except Exception:
                    self.state.update(error='本轮未完成；检查网络或重新启动。没有据此发送提醒。', stage='本轮检查失败')
                    delay = 60
            self.state['next_scan'] = time.time()+delay
            self.wake.wait(delay)
            self.wake.clear()

def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log OAuth callback codes or headers.

        def allowed(self):
            return self.headers.get('Host') in ('localhost:8787', '127.0.0.1:8787')

        def reply(self, obj, code=200):
            raw = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if not self.allowed():
                return self.reply({'error': '仅允许本机访问'}, 403)
            url = urllib.parse.urlsplit(self.path)
            if url.path == '/api/status':
                return self.reply(app.status())
            if url.path == '/oauth/callback':
                q = urllib.parse.parse_qs(url.query)
                try:
                    app.auth.finish(q.get('code', [''])[0], q.get('state', [''])[0])
                    cfg = app.store.config()
                    cfg['mail_enabled'] = True
                    app.store.put('config', cfg)
                    app.state['mail_error'] = None
                    app.wake.set()
                    target = '/?login=ok'
                except (ValueError, ApiError, RuntimeError) as e:
                    app.state['mail_error'] = str(e)
                    target = '/?login=failed'
                except Exception:
                    app.state['mail_error'] = '官方登录验证失败，请重新授权 LadyGuaGua'
                    target = '/?login=failed'
                self.send_response(303)
                self.send_header('Location', target)
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                return
            if url.path != '/':
                return self.reply({'error': '页面不存在'}, 404)
            raw = (BASE/'index.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            if (not self.allowed() or self.headers.get('Origin') not in ('http://localhost:8787', 'http://127.0.0.1:8787')
                or not secrets.compare_digest(self.headers.get('X-CSRF-Token', ''), app.csrf)):
                return self.reply({'error': '请求来源校验失败'}, 403)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 0 or length > 20000:
                    raise ValueError('请求过大')
                data = json.loads(self.rfile.read(length) or b'{}')
                if self.path == '/api/config':
                    cfg = validate_config(data, app.store.config())
                    if cfg['mail_enabled'] and not app.auth.public()['connected']:
                        raise ValueError('先授权 LadyGuaGua，才能启用邮件提醒')
                    app.store.put('config', cfg)
                    app.verified_ids = set()
                    app.wake.set()
                    return self.reply({'ok': True})
                if self.path == '/api/login':
                    return self.reply({'url': app.auth.begin()})
                if self.path == '/api/scan':
                    app.store.put('paused', False)
                    app.wake.set()
                    return self.reply({'ok': True})
                if self.path == '/api/pause':
                    app.store.put('paused', True)
                    app.state['stage'] = '暂停中，正在收尾已发出的请求'
                    return self.reply({'ok': True})
                if self.path == '/api/test-mail':
                    with app.mail_lock:
                        if time.time() < app.store.get('next_test_at', 0):
                            raise ValueError('测试邮件请间隔至少 5 分钟')
                        app.store.put('next_test_at', time.time()+300)
                        mid = app.auth.send('蓝图监控测试', 'LadyGuaGua → MikeChong：邮件连接测试成功。此邮件不是捡漏通知。')
                    return self.reply({'ok': True, 'mail_id': mid})
                if self.path == '/api/retry-mail':
                    app.store.execute("UPDATE delivery SET state='pending' WHERE state='error'")
                    app.store.put('next_mail_at', 0)
                    app.wake.set()
                    return self.reply({'ok': True})
                if self.path == '/api/disconnect':
                    with app.mail_lock, app.auth.lock:
                        cfg = app.store.config()
                        cfg['mail_enabled'] = False
                        app.store.put('config', cfg)
                        if app.auth.file.exists():
                            app.auth.file.unlink()
                    return self.reply({'ok': True})
                if self.path == '/api/stop':
                    app.stop.set()
                    app.wake.set()
                    self.reply({'ok': True})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                return self.reply({'error': '操作不存在'}, 404)
            except (ValueError, ApiError, UncertainSend, RuntimeError) as e:
                return self.reply({'error': str(e)}, 400)
            except Exception:
                return self.reply({'error': '操作未完成，请查看连接状态后重试'}, 500)
    return Handler

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default=str(BASE/'data'))
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--limit', type=int, default=160)
    parser.add_argument('--no-worker', action='store_true')
    args = parser.parse_args()
    app = Monitor(args.data_dir)
    if args.once:
        app.scan(args.limit)
        print(json.dumps(app.state, ensure_ascii=False))
        return
    server = ThreadingHTTPServer(('127.0.0.1', 8787), make_handler(app))
    if not args.no_worker:
        threading.Thread(target=app.run, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        app.stop.set()
        server.server_close()

if __name__ == '__main__':
    main()
