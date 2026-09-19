"""Use the existing Cloudflare mail relay; never read or persist its secret."""
import hashlib
import json
import os

from core import ApiError, UncertainSend

RELAY = 'https://eve-contract-opener.99617224.workers.dev'
SENDER_ID = 2124679425
RECIPIENT_ID = 2124493042

class RelayAuth:
    def __init__(self, client):
        self.client = client

    def access(self):
        key = os.environ.get('EVE_MAIL_API_KEY')
        if not key:
            raise ValueError('缺少邮件通道的 EVE_MAIL_API_KEY，未发送邮件')
        try:
            status, _, raw = self.client.request(
                RELAY+'/api/mail-health',
                headers={'Authorization':'Bearer '+key, 'Accept':'application/json'})
            result = json.loads(raw)
        except (ApiError, json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
            raise ValueError('邮件服务健康检查失败，已停止发信') from None
        if (status != 200 or result.get('ok') is not True
                or result.get('sender_id') != SENDER_ID
                or result.get('sender_name') != 'LadyGuaGua'):
            raise ValueError('邮件服务当前发件角色不是已确认的 LadyGuaGua，已停止发信')
        return dict(character_id=SENDER_ID)

    def recipient(self):
        _, _, raw = self.client.request('https://esi.evetech.net/universe/ids', method='POST',
            data=b'["MikeChong"]', headers={'Content-Type':'application/json'})
        rows = json.loads(raw).get('characters', [])
        if not any(r.get('id') == RECIPIENT_ID and r.get('name') == 'MikeChong' for r in rows):
            raise ValueError('收信角色核验失败，未发送邮件')
        return dict(name='MikeChong', id=RECIPIENT_ID)

    def send(self, subject, body):
        self.access()
        self.recipient()
        # The permanent ledger handles contract deduplication. Relay key also
        # protects an identical payload within the relay's 48-hour window.
        key = 'booster-v1-'+hashlib.sha256((subject+'\n'+body).encode()).hexdigest()
        payload = dict(subject=subject, body=body, recipient_id=RECIPIENT_ID, idempotency_key=key)
        try:
            status, _, raw = self.client.request(RELAY+'/api/send-mail', method='POST',
                data=json.dumps(payload).encode(), headers={'Content-Type':'application/json',
                    'Authorization':'Bearer '+os.environ['EVE_MAIL_API_KEY']})
        except ApiError as e:
            if e.status == 0 or e.status >= 500:
                raise UncertainSend('旧邮件通道返回结果不确定，请在游戏中核对') from None
            raise
        try:
            result = json.loads(raw)
            if status != 200 or result.get('ok') is not True:
                raise ValueError()
            if result.get('skipped') and result.get('reason') == 'duplicate':
                return '旧通道已去重'
            if result.get('sender_id') != SENDER_ID or result.get('recipient_id') != RECIPIENT_ID:
                raise ValueError()
            if type(result.get('mail_id')) is not int:
                raise ValueError()
            return result['mail_id']
        except (ValueError, TypeError):
            raise UncertainSend('旧通道没有返回匹配角色的投递编号，请在游戏中核对') from None
