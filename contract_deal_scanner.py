from __future__ import annotations

import math
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from scanner_source import (
    PUBLIC_CONTRACTS_INDEX,
    MARKET_ORDERS_INDEX,
    DATA,
    LATEST,
    JITA_SYSTEM,
    latest_file,
    download,
    load_contracts,
    load_market_orders,
    prepare_jita_books,
    fill_book,
    truthy_series,
    fetch_many_ref,
    name_en,
    type_volume,
    station_info,
    system_info,
    security_display,
    route_jumps,
)

# Contract-market deal scanner. It deliberately values bundles conservatively.
# Instant liquidation = what current Jita buy orders can actually absorb now,
# less sales tax and a configurable hauling reserve.
ACCOUNTING_LEVEL = int(os.getenv("ACCOUNTING_LEVEL", "5"))
SALES_TAX_RATE = 0.075 * (1 - 0.11 * ACCOUNTING_LEVEL)

BROKER_FEE_RATE = float(os.getenv("MARKET_BROKER_FEE_RATE", "0.015"))
ADV_BROKER_LEVEL = int(os.getenv("ADV_BROKER_RELATIONS_LEVEL", "5"))
EXPECTED_RELISTS = int(os.getenv("EXPECTED_RELISTS", "2"))
RELIST_DISCOUNT = min(0.80, 0.50 + 0.06 * ADV_BROKER_LEVEL)
RELIST_RESERVE_RATE = BROKER_FEE_RATE * (1 - RELIST_DISCOUNT) * EXPECTED_RELISTS

MIN_CONTRACT_PRICE = float(os.getenv("DEAL_MIN_CONTRACT_PRICE", "1000000"))
MIN_PRELIM_EDGE = float(os.getenv("DEAL_MIN_PRELIM_EDGE", "8000000"))
MIN_NET_PROFIT = float(os.getenv("DEAL_MIN_NET_PROFIT", "15000000"))
MIN_NET_ROI = float(os.getenv("DEAL_MIN_NET_ROI", "0.10"))
MIN_LIST_NET_PROFIT = float(os.getenv("DEAL_MIN_LIST_NET_PROFIT", "25000000"))
MIN_LIST_NET_ROI = float(os.getenv("DEAL_MIN_LIST_NET_ROI", "0.15"))
MAX_SECURE_JUMPS = int(os.getenv("DEAL_MAX_SECURE_JUMPS", "25"))
LOCATION_PREFILTER_TOP = int(os.getenv("DEAL_LOCATION_PREFILTER_TOP", "300"))
TOP = int(os.getenv("DEAL_TOP", "100"))

# Conservative reserve rather than pretending hauling is free.
# Cost = 0 in Jita; otherwise base + volume * jumps * rate.
HAUL_BASE_ISK = float(os.getenv("DEAL_HAUL_BASE_ISK", "2000000"))
HAUL_ISK_PER_M3_JUMP = float(os.getenv("DEAL_HAUL_ISK_PER_M3_JUMP", "200"))

RESULT = LATEST / "contract_deals.csv"
ALL_RESULT = LATEST / "contract_deals_all.csv"


def safe_num(v, default=0.0):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def station_location(location_id: int):
    """Resolve NPC station, require high-sec, and compute secure Jita jumps."""
    try:
        st = station_info(int(location_id))
        sid = int(st["system_id"])
        sy = system_info(sid)
        sec = security_display(float(sy.get("security_status", 0)))
        if sec < 0.5:
            return None
        jumps = route_jumps(JITA_SYSTEM, sid, "secure")
        if jumps < 0 or jumps > MAX_SECURE_JUMPS:
            return None
        return {
            "start_location_id": int(location_id),
            "station_name": st.get("name", str(location_id)),
            "system_id": sid,
            "system_name": sy.get("name", str(sid)),
            "security": sec,
            "secure_jumps_to_jita": jumps,
        }
    except Exception:
        return None


def aggregate_items(items: pd.DataFrame):
    q = defaultdict(int)
    for r in items.itertuples(index=False):
        try:
            tid = int(r.type_id)
            qty = int(r.quantity)
        except Exception:
            continue
        if tid > 0 and qty > 0:
            q[tid] += qty
    return dict(q)


def value_contract(itemq, buy_books, sell_books):
    """Conservative market valuation of one included-item bundle."""
    buy_gross = 0.0
    replacement = 0.0
    filled_units = 0
    total_units = 0
    fully_buy_types = 0
    priced_buy_types = 0
    priced_sell_types = 0
    contributions = []

    for tid, qty in itemq.items():
        total_units += qty
        bf = fill_book(buy_books.get(int(tid), []), qty)
        sf = fill_book(sell_books.get(int(tid), []), qty)

        if bf.filled > 0:
            priced_buy_types += 1
            buy_gross += bf.value
            filled_units += bf.filled
            if bf.complete:
                fully_buy_types += 1
            contributions.append((bf.value, tid, qty, bf.filled, bf.avg_price))

        if sf.filled > 0:
            priced_sell_types += 1
            replacement += sf.value

    unit_coverage = filled_units / total_units if total_units else 0.0
    return {
        "jita_buy_gross": buy_gross,
        "jita_replacement_value": replacement,
        "buy_unit_coverage": unit_coverage,
        "fully_buy_types": fully_buy_types,
        "priced_buy_types": priced_buy_types,
        "priced_sell_types": priced_sell_types,
        "top_contributions": sorted(contributions, reverse=True)[:5],
    }


def haul_reserve(total_m3, jumps):
    if jumps <= 0:
        return 0.0
    return HAUL_BASE_ISK + max(0.0, total_m3) * max(0, jumps) * HAUL_ISK_PER_M3_JUMP


def main():
    print("deal 1) latest datasets")
    c_url, c_modified = latest_file(PUBLIC_CONTRACTS_INDEX)
    m_url, m_modified = latest_file(MARKET_ORDERS_INDEX)
    c_path = DATA / Path(c_url).name
    m_path = DATA / Path(m_url).name
    if not c_path.exists():
        download(c_url, c_path)
    if not m_path.exists():
        download(m_url, m_path)

    print("deal 2) public item-exchange contracts")
    contracts, items = load_contracts(c_path)
    contracts["contract_id"] = pd.to_numeric(contracts["contract_id"], errors="coerce").astype("Int64")
    contracts["price"] = pd.to_numeric(contracts["price"], errors="coerce").fillna(0.0)
    contracts["start_location_id"] = pd.to_numeric(contracts["start_location_id"], errors="coerce").astype("Int64")

    c = contracts[(contracts["type"] == "item_exchange") & (contracts["price"] >= MIN_CONTRACT_PRICE)].copy()
    c = c[c["start_location_id"].notna() & (c["start_location_id"] < 1_000_000_000_000)].copy()

    now = pd.Timestamp.now(tz="UTC")
    if "date_expired" in c.columns:
        exp = pd.to_datetime(c["date_expired"], utc=True, errors="coerce")
        c = c[exp.isna() | (exp > now + pd.Timedelta(minutes=20))].copy()

    valid_ids = set(c["contract_id"].dropna().astype(int))
    ii = items[items["contract_id"].isin(valid_ids)].copy()
    ii["contract_id"] = pd.to_numeric(ii["contract_id"], errors="coerce").astype("Int64")
    ii["_included"] = truthy_series(ii["is_included"])
    ii["_bpc"] = truthy_series(ii["is_blueprint_copy"])
    ii["quantity"] = pd.to_numeric(ii["quantity"], errors="coerce").fillna(0).astype(int)
    ii["type_id"] = pd.to_numeric(ii["type_id"], errors="coerce").fillna(0).astype(int)

    # Requested-item barter contracts are intentionally excluded from v1 because
    # the visible ISK price alone is not the acquisition cost.
    requested_ids = set(ii.loc[~ii["_included"], "contract_id"].dropna().astype(int))
    bpc_ids = set(ii.loc[ii["_included"] & ii["_bpc"], "contract_id"].dropna().astype(int))
    usable_ids = valid_ids - requested_ids - bpc_ids
    c = c[c["contract_id"].isin(usable_ids)].copy()
    inc = ii[ii["contract_id"].isin(usable_ids) & ii["_included"] & (ii["quantity"] > 0) & (ii["type_id"] > 0)].copy()

    print("deal 3) Jita order books")
    orders = load_market_orders(m_path)
    sell_books, buy_books = prepare_jita_books(orders)
    del orders

    grouped = {int(cid): aggregate_items(g) for cid, g in inc.groupby("contract_id", sort=False)}
    c_by_id = c.set_index("contract_id", drop=False)

    prelim = []
    print(f"deal 4) value {len(grouped)} contracts")
    for cid, itemq in grouped.items():
        if not itemq or cid not in c_by_id.index:
            continue
        cm = c_by_id.loc[cid]
        if isinstance(cm, pd.DataFrame):
            cm = cm.iloc[0]
        price = safe_num(cm.get("price"))
        v = value_contract(itemq, buy_books, sell_books)

        edge = v["jita_buy_gross"] - price
        list_edge = v["jita_replacement_value"] - price
        if max(edge, list_edge) < MIN_PRELIM_EDGE:
            continue

        prelim.append({
            "contract_id": cid,
            "contract_price": price,
            "start_location_id": int(cm["start_location_id"]),
            "date_expired": cm.get("date_expired", ""),
            "itemq": itemq,
            **v,
            "prelim_edge": edge,
            "prelim_list_edge": list_edge,
        })

    prelim.sort(key=lambda x: max(x["prelim_edge"], x["prelim_list_edge"]), reverse=True)
    prelim = prelim[:LOCATION_PREFILTER_TOP]
    print(f"deal 4) preliminary candidates={len(prelim)}")

    print("deal 5) location + highsec filter")
    loc_ids = sorted({p["start_location_id"] for p in prelim})
    locations = {}
    with ThreadPoolExecutor(max_workers=min(12, max(1, len(loc_ids)))) as ex:
        futs = {ex.submit(station_location, lid): lid for lid in loc_ids}
        for fut in as_completed(futs):
            lid = futs[fut]
            try:
                locations[lid] = fut.result()
            except Exception:
                locations[lid] = None

    surviving = [p for p in prelim if locations.get(p["start_location_id"])]
    tids = sorted({tid for p in surviving for tid in p["itemq"]})
    type_objs = fetch_many_ref("types", tids)

    rows = []
    for p in surviving:
        loc = locations[p["start_location_id"]]
        total_m3 = sum(type_volume(type_objs.get(tid)) * qty for tid, qty in p["itemq"].items())
        haul = haul_reserve(total_m3, loc["secure_jumps_to_jita"])

        sales_tax = p["jita_buy_gross"] * SALES_TAX_RATE
        instant_net = p["jita_buy_gross"] - sales_tax - p["contract_price"] - haul
        instant_base = p["contract_price"] + haul
        instant_roi = instant_net / instant_base if instant_base > 0 else 0.0

        list_broker = p["jita_replacement_value"] * BROKER_FEE_RATE
        list_tax = p["jita_replacement_value"] * SALES_TAX_RATE
        list_relist = p["jita_replacement_value"] * RELIST_RESERVE_RATE
        list_net = p["jita_replacement_value"] - list_broker - list_tax - list_relist - p["contract_price"] - haul
        list_base = p["contract_price"] + haul + list_broker + list_relist
        list_roi = list_net / list_base if list_base > 0 else 0.0

        instant_ok = instant_net >= MIN_NET_PROFIT and instant_roi >= MIN_NET_ROI
        list_ok = list_net >= MIN_LIST_NET_PROFIT and list_roi >= MIN_LIST_NET_ROI
        if not (instant_ok or list_ok):
            continue

        item_lines = []
        for tid, qty in sorted(p["itemq"].items(), key=lambda kv: kv[1], reverse=True)[:12]:
            item_lines.append(f"{name_en(type_objs.get(tid), str(tid))} x{qty}")

        contrib_lines = []
        for value, tid, qty, filled, avg_price in p["top_contributions"]:
            contrib_lines.append(f"{name_en(type_objs.get(tid), str(tid))} x{qty}≈{value/1e6:.1f}M")

        deal_class = "A 即时买单套利" if instant_ok else "B 挂单潜在套利"
        score = 0.0
        if instant_ok:
            score += min(55, max(0, instant_roi) / 0.35 * 55)
            score += min(25, max(0, instant_net) / 150_000_000 * 25)
            score += 15 * min(1.0, p["buy_unit_coverage"])
            score += 5
        else:
            score += min(40, max(0, list_roi) / 0.40 * 40)
            score += min(20, max(0, list_net) / 200_000_000 * 20)
            score += 10 * min(1.0, p["buy_unit_coverage"])

        rows.append({
            "deal_class": deal_class,
            "deal_score": round(score, 1),
            "contract_id": p["contract_id"],
            "contract_price": p["contract_price"],
            "item_type_count": len(p["itemq"]),
            "item_total_units": sum(p["itemq"].values()),
            "items": " | ".join(item_lines),
            "top_value_items": " | ".join(contrib_lines),
            "jita_buy_gross": p["jita_buy_gross"],
            "sales_tax_if_instant": sales_tax,
            "instant_liquidation_net_value": p["jita_buy_gross"] - sales_tax,
            "haul_reserve": haul,
            "instant_net_profit": instant_net,
            "instant_net_roi": instant_roi,
            "jita_replacement_value": p["jita_replacement_value"],
            "list_broker_fee": list_broker,
            "list_sales_tax": list_tax,
            "list_relist_reserve": list_relist,
            "list_net_profit_est": list_net,
            "list_net_roi_est": list_roi,
            "buy_unit_coverage": p["buy_unit_coverage"],
            "fully_buy_types": p["fully_buy_types"],
            "priced_buy_types": p["priced_buy_types"],
            "priced_sell_types": p["priced_sell_types"],
            "total_m3": total_m3,
            **loc,
            "date_expired": p["date_expired"],
            "eve_contract_url": f"https://eve-contract-opener.99617224.workers.dev/c/{p['contract_id']}",
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values(
            ["deal_class", "deal_score", "instant_net_profit", "list_net_profit_est"],
            ascending=[True, False, False, False],
            inplace=True,
        )
    ALL_RESULT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ALL_RESULT, index=False)
    df.head(TOP).to_csv(RESULT, index=False)

    a = int((df.get("deal_class", pd.Series(dtype=str)) == "A 即时买单套利").sum()) if not df.empty else 0
    b = int((df.get("deal_class", pd.Series(dtype=str)) == "B 挂单潜在套利").sum()) if not df.empty else 0
    print(f"deal done: total={len(df)} instant={a} listing={b} output={RESULT}")


if __name__ == "__main__":
    main()
