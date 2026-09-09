"""EVE Ref item types only prioritize ESI work; never authorize an alert."""
import csv
import io
import json
import tarfile
import time
import urllib.request

INDEX = 'https://data.everef.net/public-contracts/index.json'
ARCHIVE = 'https://data.everef.net/public-contracts/public-contracts-latest.v2.tar.bz2'


def parse_hints(raw, blueprint_ids):
    found = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:bz2') as archive:
        member = archive.getmember('contract_items.csv')
        if member.size > 512 * 1024 * 1024:
            raise ValueError('合同物品快照超过读取上限')
        with io.TextIOWrapper(archive.extractfile(member), encoding='utf-8', newline='') as stream:
            for row in csv.DictReader(stream):
                bp = int(row['type_id'])
                if bp in blueprint_ids:
                    found.setdefault(str(int(row['contract_id'])), set()).add(bp)
    return {cid: sorted(types) for cid, types in found.items()}


def refresh_hints(store, blueprint_ids):
    saved = store.get('snapshot_hints', {})
    now = time.time()
    if now < saved.get('next_check', 0):
        return saved
    def read(url, cap):
        req = urllib.request.Request(url, headers={'User-Agent': 'BoosterBlueprintMonitor/1.3 (eve:MikeChong)'})
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read(cap+1)
        if len(raw) > cap:
            raise ValueError('公开快照超过下载上限')
        return raw
    try:
        index = json.loads(read(INDEX, 1024 * 1024))
        entry = next(f for f in index['files'] if f['url'] == ARCHIVE)
        version = entry['last_modified']
        if saved.get('modified') != version or not saved.get('contracts'):
            hints = parse_hints(read(ARCHIVE, 32 * 1024 * 1024), blueprint_ids)
        else:
            hints = saved['contracts']
        saved = dict(contracts=hints, modified=version, next_check=now+1800, error=None)
    except Exception:
        # Stale hints remain harmless priorities, and all other candidates stay queued.
        saved = dict(saved, next_check=now+300, error='快照读取失败，继续按星域核验')
    store.put('snapshot_hints', saved)
    return saved
