"""Independent Actions entrypoint, using a dedicated public-data state branch."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from app import Monitor, validate_config
from core import BASE, DEFAULTS, utc
from relay import RelayAuth

STATE_BRANCH = 'eve-booster-monitor-state'

class GitState:
    def __init__(self, monitor):
        self.monitor = monitor
        self.parent = None

    def git(self, *args, data=None, optional=False):
        p = subprocess.run(['git', *args], input=data, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
        if p.returncode and not optional:
            # Never log raw git errors: a remote URL could contain credentials.
            raise RuntimeError('药品监控状态分支读写失败；已停止本轮，避免重复发信')
        return p

    def load(self):
        p = self.git('ls-remote', '--exit-code', 'origin', 'refs/heads/'+STATE_BRANCH, optional=True)
        if p.returncode == 2:
            return
        if p.returncode != 0:
            raise RuntimeError('无法确认远程投递记录，已停止本轮')
        self.git('fetch', '--depth=1', 'origin', 'refs/heads/'+STATE_BRANCH)
        self.parent = self.git('rev-parse', 'FETCH_HEAD').stdout.decode().strip()
        data = json.loads(self.git('show', self.parent+':state.json').stdout)
        if data.get('format') != 'eve-booster-monitor-v1':
            raise RuntimeError('状态分支内容不匹配，未覆盖原内容')
        store = self.monitor.store
        for cid, items in data.get('inspected', {}).items():
            store.execute('INSERT OR REPLACE INTO inspected VALUES (?,?)', (int(cid), json.dumps(items)))
        for r in data.get('delivery', []):
            if r['state'] == 'sending':
                r.update(state='unknown', detail='上次发信中断，请在游戏中核对')
            store.execute('INSERT OR REPLACE INTO delivery VALUES (?,?,?,?,?)',
                tuple(r[k] for k in ('contract_id','recipient','state','detail','updated')))
        store.put('next_mail_at', data.get('next_mail_at', 0))
        store.put('region_cursor', data.get('region_cursor', 0))
        store.put('unavailable_until', data.get('unavailable_until', {}))

    def save(self):
        monitor, store = self.monitor, self.monitor.store
        inspected = {str(r['id']):json.loads(r['items']) for r in store.rows('SELECT * FROM inspected')
                     if not monitor.state.get('coverage_complete') or r['id'] in monitor.active_ids}
        data = dict(format='eve-booster-monitor-v1', updated=utc(), inspected=inspected,
            delivery=store.rows('SELECT * FROM delivery ORDER BY contract_id'),
            next_mail_at=store.get('next_mail_at', 0), status=monitor.state,
            region_cursor=store.get('region_cursor', 0),
            unavailable_until=store.get('unavailable_until', {}),
            alerts=[json.loads(r['payload']) for r in store.rows('SELECT payload FROM alerts')
                    if json.loads(r['payload'])['contract_id'] in monitor.verified_ids])
        raw = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True).encode()
        blob = self.git('hash-object', '-w', '--stdin', data=raw).stdout.decode().strip()
        tree = self.git('mktree', data=f'100644 blob {blob}\tstate.json\n'.encode()).stdout.decode().strip()
        args = ['-c','user.name=EVE booster monitor','-c','user.email=actions@users.noreply.github.com',
                'commit-tree',tree,'-m','Update booster monitor public scan and delivery state']
        if self.parent:
            args += ['-p', self.parent]
        commit = self.git(*args).stdout.decode().strip()
        # No force push. A concurrent or unexpected branch change fails closed.
        self.git('push','origin',commit+':refs/heads/'+STATE_BRANCH)
        self.parent = commit

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=800)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--rounds', type=int, default=1, choices=range(1, 11))
    args = parser.parse_args()
    m = Monitor(BASE/'cloud-data')
    try:
        ledger = GitState(m)
        ledger.load()
        cfg = validate_config(json.loads((BASE/'cloud-config.json').read_text('utf-8')), DEFAULTS)
        cfg['mail_enabled'] = not args.dry_run
        m.store.put('config',cfg)
        m.auth = RelayAuth(m.client)
        m.delivery_checkpoint = ledger.save
        print('开始扫描；LadyGuaGua → MikeChong。', flush=True)
        for number in range(1, args.rounds+1):
            m.scan(max(1,min(args.limit,2400)))
            m.state['round_completed'] = number
            ledger.save()
            print(json.dumps(m.state,ensure_ascii=False),flush=True)
            if number < args.rounds and (m.state.get('item_errors') or m.state.get('region_errors')):
                deadline = max(time.time()+60, m.client.blocked_until)
                while time.time() < deadline:
                    time.sleep(min(30, deadline-time.time()))
        if m.state.get('mail_error'):
            return 2
        return 0
    except Exception as e:
        # Known exceptions contain only controlled messages; do not dump tokens,
        # response bodies, environment variables or tracebacks.
        print('本轮失败：'+str(e) if isinstance(e,(RuntimeError,ValueError)) else '本轮接口失败，未确认新的提醒。', flush=True)
        return 1
    finally:
        m.store.close()

if __name__ == '__main__':
    sys.exit(main())
