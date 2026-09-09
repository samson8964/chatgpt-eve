"""EVE PKCE login; refresh tokens encrypted by Windows DPAPI, never returned to UI."""
import base64
import ctypes
import hashlib
import html
import json
import os
import secrets
import threading
import time
import urllib.parse
from pathlib import Path

from core import ApiError, ESI, UncertainSend, utc

SENDER = 'LadyGuaGua'
RECIPIENT = 'MikeChong'
SCOPE = 'esi-mail.send_mail.v1'
CALLBACK = 'http://localhost:8787/oauth/callback'
META = 'https://login.eveonline.com/.well-known/oauth-authorization-server'

def b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip('=')

def unb64(s):
    return base64.urlsafe_b64decode(s+'='*((4-len(s)%4)%4))

def protect(raw, decrypt=False):
    if os.name != 'nt':
        raise RuntimeError('此版本的邮件授权使用 Windows 加密存储；请在 Windows 运行')
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buf = ctypes.create_string_buffer(raw)
    src = Blob(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    dst = Blob()
    crypto = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    fun = crypto.CryptUnprotectData if decrypt else crypto.CryptProtectData
    fun.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                    ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fun.restype = wintypes.BOOL
    if not fun(ctypes.byref(src), None, None, None, None, 1, ctypes.byref(dst)):
        raise RuntimeError('Windows 授权加密存储失败')
    try:
        return ctypes.string_at(dst.data, dst.size)
    finally:
        kernel.LocalFree(dst.data)

class Auth:
    def __init__(self, client, store):
        self.client, self.store = client, store
        self.file = store.directory/'mail-authorization.bin'
        self.lock = threading.RLock()
        self.pending = None
        self.metadata = None
        self.metadata_at = 0

    def meta(self):
        if not self.metadata or time.time()-self.metadata_at > 3600:
            _, _, raw = self.client.request(META)
            m = json.loads(raw)
            for key in ('authorization_endpoint', 'token_endpoint', 'jwks_uri'):
                u = urllib.parse.urlsplit(m[key])
                if u.scheme != 'https' or u.hostname != 'login.eveonline.com':
                    raise ValueError('登录服务地址验证失败')
            self.metadata, self.metadata_at = m, time.time()
        return self.metadata

    def read(self):
        if not self.file.exists():
            return None
        return json.loads(protect(self.file.read_bytes(), decrypt=True))

    def save(self, data):
        temp = self.file.with_suffix('.tmp')
        temp.write_bytes(protect(json.dumps(data).encode()))
        os.replace(temp, self.file)

    def public(self):
        try:
            token = self.read()
            return dict(connected=bool(token), sender=token['name'] if token else SENDER,
                        sender_id=token['character_id'] if token else None,
                        recipient=RECIPIENT, error=None)
        except Exception:
            return dict(connected=False, sender=SENDER, recipient=RECIPIENT,
                        error='无法读取本机授权，请重新登录')

    def begin(self):
        with self.lock:
            client_id = self.store.config()['client_id'].strip()
            if not client_id:
                raise ValueError('请先填写 EVE 应用 Client ID')
            verifier = b64(secrets.token_bytes(48))
            state = secrets.token_urlsafe(32)
            self.pending = dict(verifier=verifier, state=state, expires=time.time()+600, client_id=client_id)
            params = dict(response_type='code', client_id=client_id, redirect_uri=CALLBACK,
                          scope=SCOPE, state=state, code_challenge_method='S256',
                          code_challenge=b64(hashlib.sha256(verifier.encode()).digest()))
            return self.meta()['authorization_endpoint']+'?'+urllib.parse.urlencode(params)

    def validate(self, token, client_id):
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives import hashes
        head, body, signature = token.split('.')
        header, claims = json.loads(unb64(head)), json.loads(unb64(body))
        if header.get('alg') != 'RS256':
            raise ValueError('登录签名算法不符合预期')
        _, _, raw = self.client.request(self.meta()['jwks_uri'])
        keys = json.loads(raw)['keys']
        key = next((k for k in keys if k.get('kid') == header.get('kid') and k.get('kty') == 'RSA'), None)
        if not key:
            raise ValueError('找不到官方登录签名公钥')
        pub = rsa.RSAPublicNumbers(int.from_bytes(unb64(key['e']), 'big'),
                                  int.from_bytes(unb64(key['n']), 'big')).public_key()
        pub.verify(unb64(signature), (head+'.'+body).encode(), padding.PKCS1v15(), hashes.SHA256())
        aud = claims.get('aud', [])
        if isinstance(aud, str):
            aud = [aud]
        if ('EVE Online' not in aud or (client_id not in aud and claims.get('azp') != client_id)
            or claims.get('iss', '').rstrip('/') not in ('https://login.eveonline.com', 'login.eveonline.com')
            or claims.get('exp', 0) <= time.time() or claims.get('nbf', 0) > time.time()+30):
            raise ValueError('登录令牌的应用、签发者或有效期不符')
        scopes = claims.get('scp', [])
        if isinstance(scopes, str):
            scopes = scopes.split()
        if SCOPE not in scopes:
            raise ValueError('没有取得发送游戏邮件权限')
        if claims.get('name', '').casefold() != SENDER.casefold():
            raise ValueError(f'请授权 {SENDER}，刚才选择的角色不匹配')
        sub = claims.get('sub', '')
        if not sub.startswith('CHARACTER:EVE:') or not sub.split(':')[-1].isdigit():
            raise ValueError('角色身份验证失败')
        return claims

    def exchange(self, payload, client_id):
        _, _, raw = self.client.request(self.meta()['token_endpoint'], method='POST',
             data=urllib.parse.urlencode(payload).encode(), headers={'Content-Type': 'application/x-www-form-urlencoded'})
        tokens = json.loads(raw)
        claims = self.validate(tokens['access_token'], client_id)
        tokens.update(name=claims['name'], character_id=int(claims['sub'].split(':')[-1]),
                      expires=claims['exp'], client_id=client_id)
        self.save(tokens)
        return tokens

    def finish(self, code, state):
        with self.lock:
            p = self.pending
            if not p or time.time() > p['expires'] or not secrets.compare_digest(state, p['state']):
                raise ValueError('登录请求已过期或校验失败，请重新发起登录')
            self.pending = None
            return self.exchange(dict(grant_type='authorization_code', code=code,
                     code_verifier=p['verifier'], client_id=p['client_id'], redirect_uri=CALLBACK), p['client_id'])

    def access(self):
        with self.lock:
            token = self.read()
            if not token:
                raise ValueError(f'请先授权 {SENDER}')
            if token['client_id'] != self.store.config()['client_id']:
                raise ValueError('应用 Client ID 已改变，请重新授权')
            if token['expires'] < time.time()+90:
                token = self.exchange(dict(grant_type='refresh_token', refresh_token=token['refresh_token'],
                                      client_id=token['client_id']), token['client_id'])
            return token

    def recipient(self):
        saved = self.store.get('recipient')
        if saved and saved['name'].casefold() == RECIPIENT.casefold():
            return saved
        _, _, raw = self.client.request(ESI+'/universe/ids', method='POST',
                data=json.dumps([RECIPIENT]).encode(), headers={'Content-Type': 'application/json'})
        match = next((c for c in json.loads(raw).get('characters', []) if c['name'].casefold() == RECIPIENT.casefold()), None)
        if not match:
            raise ValueError(f'未找到宁静服角色 {RECIPIENT}')
        self.store.put('recipient', match)
        return match

    def send(self, subject, body):
        token = self.access()
        receiver = self.recipient()
        if receiver['id'] == token['character_id']:
            raise ValueError('发信与收信角色相同，已阻止发送')
        payload = dict(approved_cost=0, subject=subject, body=body,
                       recipients=[dict(recipient_id=receiver['id'], recipient_type='character')])
        status, _, raw = self.client.request(ESI+f"/characters/{token['character_id']}/mail", method='POST',
            data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json',
                                                       'Authorization': 'Bearer '+token['access_token']})
        if status != 201:
            raise UncertainSend('邮件返回结果未确认，需在游戏中核对')
        return json.loads(raw)

def digest(rows):
    lines = ['超强增效剂蓝图机会提醒', '以下为公开合同报价及制造估算，未购买。',
             '基础用量从气体自制，材料取吉他卖单；成品取星域近期成交参考价。',
             '已扣设定的销售费用和额外费用预留；实际成交、建筑成本及销量可能不同。',
             '远地交货未取得实际运输报价；玩家建筑的停靠与取货权限须自行核对。',
             'ESI 有缓存，合同可能已被接受；请核对游戏中的价格、物品和剩余流程。', '']
    for r in rows:
        lines.extend([f"{r['name']}：{r['copies']} 张，共 {r['runs']} 流程",
            f"合同总价 {r['price']/1e8:.2f} 亿；折算 50 流程 {r['price']*50/r['runs']/1e8:.2f} 亿",
            f"预计总利润 {r['profit']/1e8:.2f} 亿；每 50 流程 {r['profit50']/1e8:.2f} 亿；回报率 {r['roi']:.0%}",
            f"成品七天成交 {r['week_volume']} 个（截至 {r['history_end']}）",
            f"星域编号 {r.get('region_id', '未知')}；交货地点编号 {r['location_id']}；合同编号 {r['contract_id']}",
            f"详情：https://www.adam4eve.eu/contract.php?id={r['contract_id']}", ''])
    # Do not interpolate untrusted contract titles into in-game markup.
    body = '<br>'.join(html.escape(s) for s in lines)
    body += '<br>'.join(f'<url=contract:0//{int(r["contract_id"])}>在游戏中打开合同 {int(r["contract_id"])}</url>' for r in rows)
    return f'蓝图捡漏：{len(rows)} 个合同符合门槛', body
