"""Independent Actions entrypoint, using a dedicated public-data state branch."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from app import validate_config
from monitor_v2 import OpportunityMonitor
from core import ApiError, BASE, DEFAULTS, utc
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

        raw = self.git('show', self.parent+':state.json').stdout
        if not raw.strip():
            raise RuntimeError('状态分支 state.json 为空；已停止本轮，避免重置投递次数或重复发信')
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise RuntimeError('状态分支 state.json 不是有效 JSON；已停止本轮，避免重复发信') from None
        if data.get('format') != 'eve-booster-monitor-v1':
            raise RuntimeError('状态分支内容不匹配，未覆盖原内容')

        store = self.monitor.store
        for cid, items in data.get('inspected', {}).items():
            store.execute('INSERT OR REPLACE INTO inspected VALUES (?,?)', (int(cid), json.dumps(items)))
        legacy_delivery = data.get('delivery', [])
        for r in legacy_delivery:
            if r['state'] == 'sending':
                r.update(state='unknown', detail='上次发信中断，请在游戏中核对')
            store.execute('INSERT OR REPLACE INTO delivery VALUES (?,?,?,?,?)',
                tuple(r[k] for k in ('contract_id','recipient','state','detail','updated')))

        # New repeat-count ledger. If this is the first v2 run, migrate successful
        # legacy manufacturing deliveries as one historical push.
        push_state = data.get('push_state')
        if not isinstance(push_state, dict):
            push_state = {}
            for r in legacy_delivery:
                if r.get('state') == 'sent':
                    key = f"booster-manufacturing:{int(r['recipient'])}:{int(r['contract_id'])}"
                    push_state[key] = dict(count=1, state='sent',
                                           detail=r.get('detail', '历史投递记录'),
                                           updated=r.get('updated', 0))
                elif r.get('state') in ('sending', 'unknown'):
                    key = f"booster-manufacturing:{int(r['recipient'])}:{int(r['contract_id'])}"
                    push_state[key] = dict(count=0, state='unknown',
                                           detail=r.get('detail', '历史投递结果未确认'),
                                           updated=r.get('updated', 0))
        store.put('push_state', push_state)

        legacy_next = data.get('next_mail_at', 0)
        store.put('next_mail_at_booster-manufacturing',
                  data.get('next_mail_at_booster-manufacturing', legacy_next))
        store.put('next_mail_at_booster-spread',
                  data.get('next_mail_at_booster-spread', 0))
        store.put('next_mail_at', legacy_next)
        store.put('region_cursor', data.get('region_cursor', 0))
        store.put('unavailable_until', data.get('unavailable_until', {}))

    def save(self):
        monitor, store = self.monitor, self.monitor.store
        inspected = {str(r['id']):json.loads(r['items']) for r in store.rows('SELECT * FROM inspected')
                     if not monitor.state.get('coverage_complete') or r['id'] in monitor.active_ids}
        data = dict(format='eve-booster-monitor-v1', updated=utc(), inspected=inspected,
            delivery=store.rows('SELECT * FROM delivery ORDER BY contract_id'),
            push_state=store.get('push_state', {}),
            next_mail_at=store.get('next_mail_at', 0),
            **{
                'next_mail_at_booster-manufacturing':
                    store.get('next_mail_at_booster-manufacturing', 0),
                'next_mail_at_booster-spread':
                    store.get('next_mail_at_booster-spread', 0),
            },
            status=monitor.state,
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
    m = OpportunityMonitor(BASE/'cloud-data')
    try:
        ledger = GitState(m)
        ledger.load()
        cfg = validate_config(json.loads((BASE/'cloud-config.json').read_text('utf-8')), DEFAULTS)
        cfg['mail_enabled'] = not args.dry_run
        m.store.put('config',cfg)
        m.auth = RelayAuth(m.client)
        m.delivery_checkpoint = ledger.save
        print('开始扫描；LadyGuaGua → MikeChong。制造利润与同种蓝图每流程价差独立推送。', flush=True)
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
    except ApiError as e:
        stage = m.state.get('stage', '准备阶段')
        print(f'本轮失败（阶段：{stage}）：{e}', flush=True)
        return 1
    except (RuntimeError, ValueError) as e:
        stage = m.state.get('stage', '准备阶段')
        print(f'本轮失败（阶段：{stage}）：{e}', flush=True)
        return 1
    except Exception:
        stage = m.state.get('stage', '准备阶段')
        print(f'本轮接口失败（阶段：{stage}），未确认新的提醒。', flush=True)
        return 1
    finally:
        m.store.close()


if __name__ == '__main__':
    sys.exit(main())
