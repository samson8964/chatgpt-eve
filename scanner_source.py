from __future__ import annotations

import json
import math
import os
import re
import sys
import tarfile
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Iterable

import numpy as np
import pandas as pd
import requests

PUBLIC_CONTRACTS_INDEX = "https://data.everef.net/public-contracts/index.json"
MARKET_ORDERS_INDEX = "https://data.everef.net/market-orders/index.json"
REFDATA = "https://ref-data.everef.net"
INDUSTRY_COST_API = "https://api.everef.net/v1/industry/cost"
ESI = "https://esi.evetech.net/latest"

JITA_44 = 60003760
JITA_SYSTEM = 30000142
THE_FORGE = 10000002

UA = "chatgpt-eve-bpc-sniper/3.1 (public EVE data research)"

TRUE_CAPITAL_GROUPS = {"carrier", "dreadnought", "force auxiliary", "capital industrial ship", "lancer dreadnought"}
SUPERCAP_GROUPS = {"supercarrier", "titan"}

# Strategy defaults. Override with environment variables if needed.
ACCOUNTING_LEVEL = int(os.getenv("ACCOUNTING_LEVEL", "5"))
MIN_NET_PROFIT = float(os.getenv("MIN_NET_PROFIT", "10000000"))
MIN_NET_ROI = float(os.getenv("MIN_NET_ROI", "0.02"))
PREFILTER_TOP = int(os.getenv("PREFILTER_TOP", "800"))
TOP = int(os.getenv("TOP", "100"))
MIN_HOURS_TO_EXPIRE = float(os.getenv("MIN_HOURS_TO_EXPIRE", "2"))
HIGHSEC_MAX_JUMPS_FROM_JITA = int(os.getenv("HIGHSEC_MAX_JUMPS_FROM_JITA", "15"))
HIGHSEC_FACTORY_CANDIDATES = int(os.getenv("HIGHSEC_FACTORY_CANDIDATES", "6"))
NPC_FACILITY_TAX = float(os.getenv("NPC_FACILITY_TAX", "0.0025"))
HIGHSEC_HAUL_ISK_PER_M3 = float(os.getenv("HIGHSEC_HAUL_ISK_PER_M3", "0"))
WORKERS = int(os.getenv("WORKERS", "12"))

RESULTS = Path("results")
LATEST = RESULTS / "latest"
STATE = RESULTS / "state"
CACHE = Path(".cache")
DATA = Path(".data")
for p in (LATEST, STATE, CACHE, DATA):
    p.mkdir(parents=True, exist_ok=True)


@dataclass
class Fill:
    complete: bool
    value: float
    filled: int
    avg_price: float
    best_price: float
    worst_price: float


def truthy_series(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.fillna(False)
    return s.fillna(False).astype(str).str.lower().isin(["true", "1", "t", "yes"])


def get_json(url, params=None, timeout=60, tries=4):
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=timeout)
            r.raise_for_status()
            return r.json(), r.headers
        except Exception as e:
            last = e
            if i + 1 < tries:
                time.sleep(1.2 * (i + 1))
    raise RuntimeError(f"GET failed: {url}: {last}")


def latest_file(index_url):
    idx, _ = get_json(index_url, params={"_": int(time.time())})
    files = idx.get("files") or []
    if not files:
        raise RuntimeError(f"No files in index: {index_url}")
    f = sorted(files, key=lambda x: x.get("last_modified", ""), reverse=True)[0]
    return f["url"], f.get("last_modified", "")


def download(url, path: Path):
    tmp = path.with_suffix(path.suffix + ".part")
    with requests.get(url, headers={"User-Agent": UA}, stream=True, timeout=360) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0) or 0)
        done = 0
        with tmp.open("wb") as fh:
            for chunk in r.iter_content(1024 * 1024):
                if not chunk:
                    continue
                fh.write(chunk)
                done += len(chunk)
                if total:
                    print(f"download {done/1e6:.1f}/{total/1e6:.1f} MB", end="\r")
        print()
    tmp.replace(path)


def load_contracts(tar_path: Path):
    with tarfile.open(tar_path, mode="r:bz2") as tf:
        names = tf.getnames()
        c_name = next((n for n in names if n.rstrip("/").endswith("contracts.csv")), None)
        i_name = next((n for n in names if n.rstrip("/").endswith("contract_items.csv")), None)
        if not c_name or not i_name:
            raise RuntimeError("Archive missing contracts.csv / contract_items.csv")
        contracts = pd.read_csv(tf.extractfile(c_name), low_memory=False)
        items = pd.read_csv(tf.extractfile(i_name), low_memory=False)
    return contracts, items


def load_market_orders(path: Path):
    return pd.read_csv(path, compression="bz2", low_memory=False)


def cache_file(kind: str, obj_id) -> Path:
    p = CACHE / kind
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{obj_id}.json"


def cache_get(kind, obj_id):
    p = cache_file(kind, obj_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:
        return None


def cache_put(kind, obj_id, data):
    cache_file(kind, obj_id).write_text(json.dumps(data, ensure_ascii=False), "utf-8")


def fetch_ref_obj(kind: str, obj_id: int):
    c = cache_get(kind, obj_id)
    if c is not None:
        return c
    url_kind = {"blueprints": "blueprints", "types": "types", "groups": "groups"}[kind]
    try:
        d, _ = get_json(f"{REFDATA}/{url_kind}/{int(obj_id)}", timeout=45, tries=3)
        cache_put(kind, obj_id, d)
        return d
    except Exception:
        return None


def fetch_many_ref(kind: str, ids: Iterable[int]):
    ids = sorted({int(x) for x in ids if pd.notna(x)})
    out, missing = {}, []
    for x in ids:
        c = cache_get(kind, x)
        if c is None:
            missing.append(x)
        else:
            out[x] = c
    if missing:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(fetch_ref_obj, kind, x): x for x in missing}
            for fut in as_completed(futs):
                x = futs[fut]
                try:
                    d = fut.result()
                    if d:
                        out[x] = d
                except Exception:
                    pass
    return out


def name_en(obj, fallback=""):
    if not obj:
        return fallback
    n = obj.get("name")
    if isinstance(n, str):
        return n
    if isinstance(n, dict):
        return n.get("en") or n.get("zh") or next(iter(n.values()), fallback)
    return obj.get("name_en") or fallback


def manufacturing_recipe(bp):
    try:
        m = bp["activities"]["manufacturing"]
        mats = {int(v.get("type_id", k)): int(v["quantity"]) for k, v in (m.get("materials") or {}).items()}
        prods = {int(v.get("type_id", k)): int(v["quantity"]) for k, v in (m.get("products") or {}).items()}
        if not mats or not prods:
            return None
        return mats, prods
    except Exception:
        return None


def material_units_for_job(base_qty, runs, me):
    raw = base_qty * runs * (1.0 - me / 100.0)
    return max(int(runs), int(math.ceil(raw - 1e-10)))


def type_group_id(obj):
    if not obj:
        return None
    for k in ("group_id", "groupID"):
        if obj.get(k) is not None:
            try:
                return int(obj[k])
            except Exception:
                pass
    return None


def type_volume(obj):
    if not obj:
        return 0.0
    for k in ("packaged_volume", "volume"):
        if obj.get(k) is not None:
            try:
                return float(obj[k])
            except Exception:
                pass
    return 0.0


def parse_iso_hours(s):
    if not s:
        return 0.0
    m = re.fullmatch(r"P(?:(?P<d>[\d.]+)D)?T?(?:(?P<h>[\d.]+)H)?(?:(?P<m>[\d.]+)M)?(?:(?P<s>[\d.]+)S)?", str(s))
    if not m:
        return 0.0
    return float(m.group("d") or 0) * 24 + float(m.group("h") or 0) + float(m.group("m") or 0) / 60 + float(m.group("s") or 0) / 3600


def esi_get(path, params=None, cache_key=None, refresh=False):
    if cache_key and not refresh:
        c = cache_get("esi", cache_key)
        if c is not None:
            return c
    d, _ = get_json(f"{ESI}{path}", params=params or {"datasource": "tranquility"}, timeout=60, tries=4)
    if cache_key:
        cache_put("esi", cache_key, d)
    return d


def route_jumps(origin, dest, flag="shortest"):
    if origin == dest:
        return 0
    key = f"route_{origin}_{dest}_{flag}"
    c = cache_get("esi", key)
    if c is not None:
        return int(c["jumps"])
    try:
        arr = esi_get(f"/route/{origin}/{dest}/", {"datasource": "tranquility", "flag": flag})
        jumps = max(0, len(arr) - 1)
    except Exception:
        jumps = -1
    cache_put("esi", key, {"jumps": jumps})
    return jumps


def industry_indices():
    arr = esi_get("/industry/systems/", {"datasource": "tranquility", "_": int(time.time())}, refresh=True)
    out = {}
    for row in arr:
        for ci in row.get("cost_indices", []):
            if ci.get("activity") == "manufacturing":
                out[int(row["solar_system_id"])] = float(ci.get("cost_index", 0.0))
                break
    return out


def discover_region_systems(region_id: int):
    reg = esi_get(f"/universe/regions/{region_id}/", cache_key=f"region_{region_id}")
    systems = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {
            ex.submit(esi_get, f"/universe/constellations/{int(cid)}/", None, f"constellation_{int(cid)}", False): cid
            for cid in reg.get("constellations", [])
        }
        for fut in as_completed(futs):
            try:
                systems.extend(fut.result().get("systems", []))
            except Exception:
                pass
    return sorted({int(x) for x in systems})


def system_info(sid):
    return esi_get(f"/universe/systems/{sid}/", cache_key=f"system_{sid}")


def station_info(stid):
    return esi_get(f"/universe/stations/{stid}/", cache_key=f"station_{stid}")


def security_display(sec):
    return math.floor(float(sec) * 10 + 0.5) / 10.0


def station_has_factory(st):
    services = [str(x).lower() for x in st.get("services", [])]
    return any(("factory" in s) or ("manufactur" in s) for s in services)


def discover_highsec_factories():
    indices = industry_indices()
    candidates = []
    systems = discover_region_systems(THE_FORGE)
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        infos = {ex.submit(system_info, sid): sid for sid in systems}
        for fut in as_completed(infos):
            sid = infos[fut]
            try:
                s = fut.result()
            except Exception:
                continue
            if security_display(float(s.get("security_status", 0))) < 0.5:
                continue
            stations = [int(x) for x in s.get("stations", [])]
            if not stations:
                continue
            factory_station = None
            factory_station_id = None
            for stid in stations:
                try:
                    st = station_info(stid)
                    if station_has_factory(st):
                        factory_station = st
                        factory_station_id = stid
                        break
                except Exception:
                    pass
            if not factory_station:
                continue
            jumps = route_jumps(JITA_SYSTEM, sid, "secure")
            if jumps < 0 or jumps > HIGHSEC_MAX_JUMPS_FROM_JITA:
                continue
            candidates.append({
                "system_id": sid,
                "system_name": s.get("name", str(sid)),
                "station_id": int(factory_station_id),
                "station_name": factory_station.get("name", str(factory_station_id)),
                "sci": float(indices.get(sid, 0.0)),
                "jumps": jumps,
            })
    candidates.sort(key=lambda x: (x["sci"], x["jumps"]))
    return candidates[:HIGHSEC_FACTORY_CANDIDATES]


def prepare_jita_books(orders: pd.DataFrame):
    b = truthy_series(orders["is_buy_order"])
    loc_col = "location_id" if "location_id" in orders.columns else "station_id"
    common = (orders["region_id"] == THE_FORGE) & orders[loc_col].eq(JITA_44)
    cols = ["type_id", "price", "volume_remain", "min_volume"]
    sells = orders.loc[common & ~b, cols].copy()
    buys = orders.loc[common & b, cols].copy()
    for o in (sells, buys):
        o["type_id"] = pd.to_numeric(o["type_id"], errors="coerce").fillna(0).astype(int)
        o["price"] = pd.to_numeric(o["price"], errors="coerce").fillna(0.0)
        o["volume_remain"] = pd.to_numeric(o["volume_remain"], errors="coerce").fillna(0).astype(int)
        o["min_volume"] = pd.to_numeric(o["min_volume"], errors="coerce").fillna(1).astype(int)
        o.drop(o[o["volume_remain"] <= 0].index, inplace=True)
    sells.sort_values(["type_id", "price"], ascending=[True, True], inplace=True)
    buys.sort_values(["type_id", "price"], ascending=[True, False], inplace=True)
    sb, bb = defaultdict(list), defaultdict(list)
    for r in sells.itertuples(index=False):
        sb[int(r.type_id)].append({"price": float(r.price), "vol": int(r.volume_remain), "min": int(r.min_volume)})
    for r in buys.itertuples(index=False):
        bb[int(r.type_id)].append({"price": float(r.price), "vol": int(r.volume_remain), "min": int(r.min_volume)})
    return sb, bb


def fill_book(book, qty):
    if qty <= 0:
        return Fill(True, 0.0, 0, 0.0, 0.0, 0.0)
    left, value, prices, filled = int(qty), 0.0, [], 0
    for o in book:
        if left <= 0:
            break
        take = min(left, int(o.get("vol", 0)))
        if take < max(1, int(o.get("min", 1))):
            continue
        p = float(o["price"])
        value += p * take
        filled += take
        left -= take
        prices.append(p)
    return Fill(left == 0, value, filled, value / filled if filled else 0, prices[0] if prices else 0, prices[-1] if prices else 0)


def industry_quote(bp_tid, product_tid, runs, me, te, system_id):
    key = f"{bp_tid}_{product_tid}_{runs}_{me}_{te}_{system_id}_{NPC_FACILITY_TAX:.6f}"
    # cache for one run only; index changes, so not persisted across days intentionally
    params = {
        "product_id": int(product_tid), "blueprint_id": int(bp_tid), "runs": int(runs),
        "me": int(me), "te": int(te), "system_id": int(system_id),
        "facility_tax": float(NPC_FACILITY_TAX), "industry": 5, "advanced_industry": 5,
    }
    try:
        d, _ = get_json(INDUSTRY_COST_API, params=params, timeout=60, tries=4)
        m = d.get("manufacturing", {})
        row = m.get(str(int(product_tid))) or m.get(int(product_tid)) or (next(iter(m.values())) if m else None)
        if not row:
            return None
        return {"job_cost": float(row.get("total_job_cost", 0.0)), "time_hours": parse_iso_hours(row.get("time"))}
    except Exception:
        return None


def market_history(type_id: int):
    try:
        arr = esi_get(f"/markets/{THE_FORGE}/history/", {"datasource": "tranquility", "type_id": int(type_id)})
        if not arr:
            return {}
        df = pd.DataFrame(arr)
        df["date"] = pd.to_datetime(df["date"], utc=True)
        df = df.sort_values("date")
        cutoff30 = pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=30)
        cutoff7 = pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=7)
        d30 = df[df["date"] >= cutoff30]
        d7 = df[df["date"] >= cutoff7]
        def agg(x):
            if x.empty:
                return (0.0, 0.0, 0.0)
            vol = pd.to_numeric(x["volume"], errors="coerce").fillna(0)
            avg = (pd.to_numeric(x["average"], errors="coerce").fillna(0) * vol).sum() / vol.sum() if vol.sum() else 0
            return float(vol.mean()), float(avg), float(pd.to_numeric(x.get("order_count", 0), errors="coerce").fillna(0).sum())
        av7, v7, _ = agg(d7)
        av30, v30, oc30 = agg(d30)
        return {
            "market_history_days": float(len(d30)),
            "avg_daily_volume_7d": av7,
            "avg_daily_volume_30d": av30,
            "vwap_7d": v7,
            "vwap_30d": v30,
            "order_count_30d": oc30,
        }
    except Exception:
        return {}


def score_row(r):
    # 0-100 heuristic: ROI, liquidity, market capacity, price normality, persistence.
    roi = float(r.get("net_roi", 0) or 0)
    vol_days = float(r.get("output_days_of_30d_volume", 99) or 99)
    cap = float(r.get("market_capacity_contracts", 0) or 0)
    premium = abs(float(r.get("current_bid_premium_vs_30d", 0) or 0))
    persistence = float(r.get("persistence_7d", 0) or 0)
    scan_days = int(r.get("scan_days_7d", 0) or 0)

    s = 0.0
    s += min(30, max(0, roi) / 0.20 * 30)
    s += max(0, 20 * (1 - min(vol_days, 2.0) / 2.0))
    s += min(15, cap / 10 * 15)
    s += max(0, 15 * (1 - min(premium, 0.30) / 0.30))
    if scan_days >= 3:
        s += 20 * persistence
    else:
        s += 10
    return round(s, 1)


def classify_row(r):
    cap = float(r.get("market_capacity_contracts", 0) or 0)
    premium = float(r.get("current_bid_premium_vs_30d", 0) or 0)
    scan_days = int(r.get("scan_days_7d", 0) or 0)
    persistence = float(r.get("persistence_7d", 0) or 0)
    if cap < 1:
        return "排除：盈利买盘不足", "D：不做"
    if premium > 0.15 and cap <= 1:
        return "价格异常型瞬时机会", "C：抢单型，先确认买盘"
    if cap <= 1:
        return "深度不足型瞬时机会", "C：抢单型，先确认买盘"
    if scan_days >= 5 and persistence >= 0.7:
        return "持续机会", "A：重点关注"
    if scan_days >= 3 and persistence >= 0.5:
        return "周期机会", "B+：可重点做"
    return "新机会/待观察", "B-：当前不错，继续观察"


def run_scan():
    print("1) latest datasets")
    c_url, c_modified = latest_file(PUBLIC_CONTRACTS_INDEX)
    m_url, m_modified = latest_file(MARKET_ORDERS_INDEX)
    c_path = DATA / Path(c_url).name
    m_path = DATA / Path(m_url).name
    if not c_path.exists(): download(c_url, c_path)
    if not m_path.exists(): download(m_url, m_path)

    print("2) factories")
    factories = discover_highsec_factories()
    if not factories:
        raise RuntimeError("No highsec NPC factory found in The Forge")
    print(factories)

    print("3) contracts")
    contracts, items = load_contracts(c_path)
    contracts["contract_id"] = pd.to_numeric(contracts["contract_id"], errors="coerce").astype("Int64")
    contracts["price"] = pd.to_numeric(contracts["price"], errors="coerce").fillna(0.0)
    c = contracts[(contracts["type"] == "item_exchange") & (contracts["price"] > 0)].copy()
    now = pd.Timestamp.now(tz="UTC")
    if "date_expired" in c.columns:
        exp = pd.to_datetime(c["date_expired"], utc=True, errors="coerce")
        c = c[exp.isna() | (((exp - now).dt.total_seconds() / 3600) >= MIN_HOURS_TO_EXPIRE)].copy()
    # public structures can be inaccessible; keep NPC stations only
    sl = pd.to_numeric(c["start_location_id"], errors="coerce")
    c = c[sl.isna() | (sl < 1_000_000_000_000)].copy()
    valid_ids = set(c["contract_id"].dropna().astype(int))

    items["contract_id"] = pd.to_numeric(items["contract_id"], errors="coerce").astype("Int64")
    ii = items[items["contract_id"].isin(valid_ids)].copy()
    ii["_included"] = truthy_series(ii["is_included"])
    ii["_bpc"] = truthy_series(ii["is_blueprint_copy"])
    bad_requested = set(ii.loc[~ii["_included"], "contract_id"].dropna().astype(int))
    bad_extra = set(ii.loc[ii["_included"] & ~ii["_bpc"], "contract_id"].dropna().astype(int))
    bpc = ii[ii["_included"] & ii["_bpc"]].copy()
    for col, default in [("runs",0),("material_efficiency",0),("time_efficiency",0),("quantity",1),("type_id",0)]:
        bpc[col] = pd.to_numeric(bpc[col], errors="coerce").fillna(default).astype(int)
    bpc = bpc[(bpc["runs"] > 0) & (bpc["type_id"] > 0)]
    good = set(bpc["contract_id"].astype(int)) - bad_requested - bad_extra
    c = c[c["contract_id"].isin(good)].copy()
    bpc = bpc[bpc["contract_id"].isin(good)].copy()

    print("4) recipes + books")
    bp_ids = bpc["type_id"].unique().tolist()
    bp_defs = fetch_many_ref("blueprints", bp_ids)
    recipes = {int(t): manufacturing_recipe(o) for t,o in bp_defs.items() if manufacturing_recipe(o)}
    bpc = bpc[bpc["type_id"].isin(recipes.keys())]
    c = c[c["contract_id"].isin(set(bpc["contract_id"].astype(int)))]
    orders = load_market_orders(m_path)
    sell_books, buy_books = prepare_jita_books(orders)
    del orders

    all_type_ids = set(bp_ids)
    for mats, prods in recipes.values():
        all_type_ids.update(mats); all_type_ids.update(prods)
    type_objs = fetch_many_ref("types", all_type_ids)
    group_ids = {type_group_id(o) for o in type_objs.values()}
    group_ids.discard(None)
    group_objs = fetch_many_ref("groups", group_ids)
    product_class = {}
    for tid, tobj in type_objs.items():
        gid = type_group_id(tobj)
        gname = name_en(group_objs.get(gid), "").strip().lower()
        if gname in SUPERCAP_GROUPS:
            product_class[int(tid)] = "supercapital"
        elif gname in TRUE_CAPITAL_GROUPS:
            product_class[int(tid)] = "true_capital"
        else:
            product_class[int(tid)] = "normal"

    print("5) prefilter")
    c_by_id = c.set_index("contract_id", drop=False).to_dict("index")
    prelim, excluded = [], []
    for cid_raw, g in bpc.groupby("contract_id", sort=False):
        cid = int(cid_raw); cm = c_by_id.get(cid)
        if not cm: continue
        matq, prodq, jobs, total_runs = defaultdict(int), defaultdict(int), [], 0
        ok = True
        for r in g.itertuples(index=False):
            bp_tid, runs, me, te, copies = int(r.type_id), int(r.runs), int(r.material_efficiency), int(r.time_efficiency), max(1,int(r.quantity))
            rec = recipes.get(bp_tid)
            if not rec: ok=False; break
            mats, prods = rec
            for mtid, base in mats.items(): matq[int(mtid)] += material_units_for_job(base, runs, me) * copies
            for ptid, upr in prods.items(): prodq[int(ptid)] += int(upr) * runs * copies
            jobs.append({"bp_tid":bp_tid,"product_tid":int(next(iter(prods.keys()))),"runs":runs,"me":me,"te":te,"copies":copies})
            total_runs += runs * copies
        if not ok or not matq or not prodq: continue
        classes = {product_class.get(int(tid), "normal") for tid in prodq}
        if "supercapital" in classes:
            excluded.append({"contract_id":cid,"reason":"SUPER_CAPITAL_REQUIRES_SPECIAL_SOV_NULL_FACILITY"}); continue
        if "true_capital" in classes:
            excluded.append({"contract_id":cid,"reason":"TRUE_CAPITAL_NOT_SUPPORTED_IN_HIGHSEC_AUTOMATION"}); continue
        material_cost = 0.0
        for tid, qty in matq.items():
            f=fill_book(sell_books.get(tid,[]),qty)
            if not f.complete: ok=False; break
            material_cost += f.value
        if not ok:
            excluded.append({"contract_id":cid,"reason":"INSUFFICIENT_JITA_MATERIAL_SELL_DEPTH"}); continue
        revenue = 0.0
        for tid, qty in prodq.items():
            f=fill_book(buy_books.get(tid,[]),qty)
            if not f.complete: ok=False; break
            revenue += f.value
        if not ok:
            excluded.append({"contract_id":cid,"reason":"INSUFFICIENT_JITA_BUY_DEPTH"}); continue
        cp=float(cm.get("price",0) or 0)
        if revenue - cp - material_cost < MIN_NET_PROFIT: continue
        haul_m3 = sum(type_volume(type_objs.get(tid))*qty for tid,qty in matq.items()) + sum(type_volume(type_objs.get(tid))*qty for tid,qty in prodq.items())
        prelim.append({"contract_id":cid,"cm":cm,"contract_price":cp,"material_cost":material_cost,"gross_revenue":revenue,"matq":dict(matq),"prodq":dict(prodq),"jobs":jobs,"total_runs":total_runs,"haul_m3":haul_m3})
    prelim.sort(key=lambda x: x["gross_revenue"]-x["contract_price"]-x["material_cost"], reverse=True)
    prelim = prelim[:PREFILTER_TOP]

    print("6) exact fees")
    tax_rate = max(0.0, 0.075 * (1 - 0.11 * ACCOUNTING_LEVEL))
    exact=[]
    for p in prelim:
        best=None
        for fac in factories:
            job_cost=0.0; job_hours=0.0; ok=True
            for j in p["jobs"]:
                q=industry_quote(j["bp_tid"],j["product_tid"],j["runs"],j["me"],j["te"],fac["system_id"])
                if not q: ok=False; break
                job_cost += q["job_cost"] * j["copies"]
                job_hours += q["time_hours"] * j["copies"]
            if not ok: continue
            sales_tax = p["gross_revenue"]*tax_rate
            haul_cost = p["haul_m3"]*HIGHSEC_HAUL_ISK_PER_M3
            net = p["gross_revenue"] - p["contract_price"] - p["material_cost"] - job_cost - sales_tax - haul_cost
            base = p["contract_price"] + p["material_cost"] + job_cost + haul_cost
            roi = net/base if base else 0
            cand={"fac":fac,"job_cost":job_cost,"job_hours":job_hours,"sales_tax":sales_tax,"haul_cost":haul_cost,"net":net,"roi":roi}
            if best is None or net>best["net"]: best=cand
        if not best or best["net"]<MIN_NET_PROFIT or best["roi"]<MIN_NET_ROI: continue

        cm=p["cm"]
        bp_desc=[]
        for j in p["jobs"]:
            bp_desc.append(f"{j['copies']}x {name_en(type_objs.get(j['bp_tid']), str(j['bp_tid']))} [{j['runs']} runs, ME{j['me']}/TE{j['te']}]")
        prod_desc=[]
        for tid,qty in p["prodq"].items(): prod_desc.append(f"{qty}x {name_en(type_objs.get(tid), str(tid))}")
        single=len(p["prodq"])==1
        product_tid, output_qty=(next(iter(p["prodq"].items())) if single else (np.nan,np.nan))
        market_cap=np.nan; break_even_bid=np.nan; worst_bid=np.nan
        if single:
            book=buy_books.get(int(product_tid),[])
            fixed=p["contract_price"]+p["material_cost"]+best["job_cost"]+best["haul_cost"]
            break_even_bid=fixed/(int(output_qty)*(1-tax_rate))
            profitable_units=sum(int(o["vol"]) for o in book if float(o["price"])>=break_even_bid)
            market_cap=profitable_units//int(output_qty)
            f=fill_book(book,int(output_qty)); worst_bid=f.worst_price if f.complete else np.nan
        exact.append({
            "contract_id":p["contract_id"],"blueprints":" | ".join(bp_desc),"products":" | ".join(prod_desc),
            "contract_price":p["contract_price"],"material_cost_jita_depth":p["material_cost"],"manufacturing_job_cost":best["job_cost"],
            "sales_tax":best["sales_tax"],"configured_haul_cost":best["haul_cost"],"gross_revenue":p["gross_revenue"],"net_profit":best["net"],"net_roi":best["roi"],
            "factory_system":best["fac"]["system_name"],"factory_station":best["fac"]["station_name"],"factory_sci":best["fac"]["sci"],"factory_jumps_from_jita":best["fac"]["jumps"],
            "serial_job_hours":best["job_hours"],"profit_per_serial_job_hour":best["net"]/best["job_hours"] if best["job_hours"] else 0,
            "haul_m3":p["haul_m3"],"break_even_haul_isk_per_m3":best["net"]/p["haul_m3"] if p["haul_m3"] else np.inf,
            "worst_buy_price_used":worst_bid,"break_even_bid_per_unit":break_even_bid,"market_capacity_contracts":market_cap,
            "total_bpc_runs":p["total_runs"],"bpc_cost_per_run":p["contract_price"]/p["total_runs"] if p["total_runs"] else np.nan,
            "contract_region_id":cm.get("region_id"),"contract_system_id":cm.get("system_id"),"contract_start_location_id":cm.get("start_location_id"),"date_expired":cm.get("date_expired"),"title":cm.get("title",""),
            "product_type_id":product_tid,"output_qty":output_qty,"is_single_product":single,
        })

    if not exact:
        pd.DataFrame(excluded).to_csv(LATEST/"excluded.csv",index=False,encoding="utf-8-sig")
        pd.DataFrame().to_csv(LATEST/"ranked_opportunities.csv",index=False,encoding="utf-8-sig")
        return

    df=pd.DataFrame(exact)

    print("7) market history")
    histories={}
    tids=sorted({int(x) for x in df.loc[df["is_single_product"],"product_type_id"].dropna().tolist()})
    with ThreadPoolExecutor(max_workers=min(WORKERS,8)) as ex:
        futs={ex.submit(market_history,tid):tid for tid in tids}
        for fut in as_completed(futs):
            tid=futs[fut]
            try: histories[tid]=fut.result()
            except Exception: histories[tid]={}
    for k in ["market_history_days","avg_daily_volume_7d","avg_daily_volume_30d","vwap_7d","vwap_30d","order_count_30d"]:
        df[k]=df.apply(lambda r: histories.get(int(r["product_type_id"]),{}).get(k,np.nan) if r["is_single_product"] else np.nan,axis=1)
    df["current_bid_premium_vs_30d"]=(df["worst_buy_price_used"]/df["vwap_30d"]-1).replace([np.inf,-np.inf],np.nan)
    df["output_days_of_30d_volume"]=(df["output_qty"]/df["avg_daily_volume_30d"].replace(0,np.nan))
    df["output_days_of_7d_volume"]=(df["output_qty"]/df["avg_daily_volume_7d"].replace(0,np.nan))

    print("8) persistence")
    hist_path=STATE/"opportunity_history.csv"
    if hist_path.exists():
        old=pd.read_csv(hist_path)
    else:
        old=pd.DataFrame(columns=["scan_date","product_type_id","net_roi","net_profit"])
    scan_date=datetime.now(timezone.utc).date().isoformat()
    today=df[df["is_single_product"]].groupby("product_type_id",as_index=False).agg(net_roi=("net_roi","max"),net_profit=("net_profit","max"))
    today["scan_date"]=scan_date
    hist=pd.concat([old,today],ignore_index=True)
    hist["product_type_id"]=pd.to_numeric(hist["product_type_id"],errors="coerce")
    hist=hist.dropna(subset=["product_type_id"])
    hist["product_type_id"]=hist["product_type_id"].astype(int)
    hist=hist.sort_values(["scan_date","net_roi"],ascending=[True,False]).drop_duplicates(["scan_date","product_type_id"],keep="first")
    cutoff=(datetime.now(timezone.utc).date()-timedelta(days=30)).isoformat()
    hist=hist[hist["scan_date"]>=cutoff]
    hist.to_csv(hist_path,index=False,encoding="utf-8-sig")

    metrics={}
    for tid,g in hist.groupby("product_type_id"):
        g=g.sort_values("scan_date")
        last7=g[g["scan_date"] >= (datetime.now(timezone.utc).date()-timedelta(days=6)).isoformat()]
        scan_days=len(last7); profitable=(last7["net_profit"]>=MIN_NET_PROFIT)&(last7["net_roi"]>=MIN_NET_ROI)
        metrics[int(tid)]={
            "scan_days_7d":scan_days,"profitable_days_7d":int(profitable.sum()),"persistence_7d":float(profitable.mean()) if scan_days else 0,
            "median_net_roi_7d":float(last7.loc[profitable,"net_roi"].median()) if profitable.any() else np.nan,
            "median_net_profit_7d":float(last7.loc[profitable,"net_profit"].median()) if profitable.any() else np.nan,
        }
    for k in ["scan_days_7d","profitable_days_7d","persistence_7d","median_net_roi_7d","median_net_profit_7d"]:
        df[k]=df.apply(lambda r: metrics.get(int(r["product_type_id"]),{}).get(k,np.nan) if r["is_single_product"] else np.nan,axis=1)

    print("9) rank")
    # number of profitable contracts by product in this snapshot
    counts=df[df["is_single_product"]].groupby("product_type_id")["contract_id"].count().to_dict()
    df["current_profitable_contracts"]=df.apply(lambda r: counts.get(int(r["product_type_id"]),np.nan) if r["is_single_product"] else np.nan,axis=1)
    df["opportunity_score"]=df.apply(score_row,axis=1)
    cls=df.apply(classify_row,axis=1,result_type="expand")
    df["opportunity_class"]=cls[0]; df["recommendation"]=cls[1]
    df["eve_contract_search_hint"]=df.apply(lambda r: f"{r['blueprints']} | 合同价 {r['contract_price']:.0f} ISK | 到期 {r['date_expired']}",axis=1)

    # best contract per product signature, but keep multi-product packs by contract id
    single=df[df["is_single_product"]].sort_values(["opportunity_score","net_profit"],ascending=[False,False]).drop_duplicates("product_type_id")
    multi=df[~df["is_single_product"]]
    ranked=pd.concat([single,multi],ignore_index=True).sort_values(["opportunity_score","net_profit"],ascending=[False,False]).head(TOP)

    # watchlist per product
    watch=[]
    for tid,g in df[df["is_single_product"]].groupby("product_type_id"):
        best=g.sort_values(["opportunity_score","net_profit"],ascending=[False,False]).iloc[0]
        watch.append({
            "product_type_id":int(tid),"product_name":best["products"],"last_seen":scan_date,
            "opportunity_class":best["opportunity_class"],"opportunity_score":best["opportunity_score"],"recommendation":best["recommendation"],
            "persistence_7d":best["persistence_7d"],"scan_days_7d":best["scan_days_7d"],"profitable_days_7d":best["profitable_days_7d"],
            "avg_daily_volume_30d":best["avg_daily_volume_30d"],"vwap_30d":best["vwap_30d"],"current_bid_premium_vs_30d":best["current_bid_premium_vs_30d"],
            "best_current_net_roi":best["net_roi"],"best_current_net_profit":best["net_profit"],"current_profitable_contracts":best["current_profitable_contracts"],
        })
    watch=pd.DataFrame(watch).sort_values(["opportunity_score","best_current_net_profit"],ascending=[False,False])

    df.to_csv(LATEST/"all_executable_scored.csv",index=False,encoding="utf-8-sig")
    ranked.to_csv(LATEST/"ranked_opportunities.csv",index=False,encoding="utf-8-sig")
    watch.to_csv(LATEST/"product_watchlist.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(excluded).to_csv(LATEST/"excluded.csv",index=False,encoding="utf-8-sig")
    meta={
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),"contracts_snapshot":c_modified,"market_snapshot":m_modified,
        "accounting_level":ACCOUNTING_LEVEL,"transaction_tax_rate":tax_rate,"factory_candidates":factories,
        "ranked_count":int(len(ranked)),"all_executable_count":int(len(df)),
    }
    (LATEST/"meta.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),"utf-8")
    print(ranked[["contract_id","products","net_profit","net_roi","opportunity_score","recommendation"]].head(15).to_string(index=False))


if __name__ == "__main__":
    run_scan()
