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
    latest_file,
    download,
    load_contracts,
    load_market_orders,
    prepare_jita_books,
    fill_book,
    truthy_series,
    fetch_many_ref,
    name_en,
    type_group_id,
    type_volume,
)
from contract_deal_scanner import (
    SALES_TAX_RATE,
    current_friendly_alliances,
    sovereignty_owners,
    load_structures,
    resolve_location,
    haul_reserve,
)

# Unified executable-arbitrage policy.
# Every reported profit is based ONLY on current Jita 4-4 buy-order depth.
MIN_CONTRACT_PRICE = float(os.getenv("DEAL_MIN_CONTRACT_PRICE", "1000000"))
MAX_CONTRACT_PRICE = float(os.getenv("DEAL_MAX_CONTRACT_PRICE", "5000000000"))
MIN_NET_PROFIT = float(os.getenv("DEAL_MIN_NET_PROFIT", "30000000"))
MIN_NET_ROI = float(os.getenv("DEAL_MIN_NET_ROI", "0.10"))
MIN_HOURS_TO_EXPIRE = float(os.getenv("DEAL_MIN_HOURS_TO_EXPIRE", "0.5"))
TOP = int(os.getenv("DEAL_TOP", "250"))
MULTI_TOP = int(os.getenv("MULTI_TOP", "250"))
SKIN_MAJOR_SHARE = float(os.getenv("DEAL_SKIN_MAJOR_SHARE", "0.50"))
LOCATION_WORKERS = int(os.getenv("DEAL_LOCATION_WORKERS", "12"))

SPOT_RESULT = LATEST / "contract_deals.csv"
SPOT_ALL = LATEST / "contract_deals_all.csv"
MULTI_RESULT = LATEST / "multi_item_contract_deals.csv"
MULTI_ALL = LATEST / "multi_item_contract_all.csv"

# Ship SKIN licences and SKINR/design-element inputs. Deliberately narrow enough not to
# suppress ordinary industrial materials merely because a group contains the word "material".
SKIN_KEYWORDS = (
    " skin",
    "skin ",
    "skinr",
    "nanocoating",
    "sequencing binder",
    "design element",
    "pattern projection",
    "pattern projector",
    "holographic",
)
SKIN_GROUP_KEYWORDS = (
    "skin",
    "nanocoating",
    "design element",
    "pattern projection",
)


def safe_num(v, default=0.0):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def aggregate_items(items: pd.DataFrame):
    out = defaultdict(int)
    for r in items.itertuples(index=False):
        try:
            tid = int(r.type_id)
            qty = int(r.quantity)
        except Exception:
            continue
        if tid > 0 and qty > 0:
            out[tid] += qty
    return dict(out)


def is_skin_related(tid: int, type_objs, group_objs) -> bool:
    obj = type_objs.get(int(tid))
    name = name_en(obj, "").strip().lower()
    gid = type_group_id(obj)
    group_name = name_en(group_objs.get(gid), "").strip().lower() if gid is not None else ""
    padded = f" {name} "
    return any(k in padded for k in SKIN_KEYWORDS) or any(k in group_name for k in SKIN_GROUP_KEYWORDS)


def buy_value(itemq, buy_books):
    gross = 0.0
    stress_gross = 0.0
    total_units = 0
    filled_units = 0
    rows = []
    for tid, qty in itemq.items():
        book = buy_books.get(int(tid), [])
        fill = fill_book(book, qty)
        # Stress test removes the single best visible Jita buy order for each item type.
        stress = fill_book(book[1:] if book else [], qty)
        gross += safe_num(fill.value)
        stress_gross += safe_num(stress.value)
        total_units += int(qty)
        filled_units += int(fill.filled or 0)
        rows.append(
            {
                "type_id": int(tid),
                "quantity": int(qty),
                "buy_value": safe_num(fill.value),
                "buy_filled": int(fill.filled or 0),
                "buy_complete": bool(fill.complete),
                "buy_avg": safe_num(fill.avg_price),
                "buy_best": safe_num(fill.best_price),
                "buy_worst": safe_num(fill.worst_price),
                "stress_buy_value": safe_num(stress.value),
            }
        )
    return {
        "jita_buy_gross": gross,
        "stress_jita_buy_gross": stress_gross,
        "buy_unit_coverage": filled_units / total_units if total_units else 0.0,
        "buy_filled_units": filled_units,
        "total_units": total_units,
        "type_rows": rows,
    }


def empty_outputs():
    LATEST.mkdir(parents=True, exist_ok=True)
    pd.DataFrame().to_csv(SPOT_ALL, index=False)
    pd.DataFrame().to_csv(SPOT_RESULT, index=False)
    pd.DataFrame().to_csv(MULTI_ALL, index=False)
    pd.DataFrame().to_csv(MULTI_RESULT, index=False)


def main():
    print("buy-only 1) latest public contracts + Jita orders")
    c_url, _ = latest_file(PUBLIC_CONTRACTS_INDEX)
    m_url, _ = latest_file(MARKET_ORDERS_INDEX)
    c_path = DATA / Path(c_url).name
    m_path = DATA / Path(m_url).name
    if not c_path.exists():
        download(c_url, c_path)
    if not m_path.exists():
        download(m_url, m_path)

    contracts, items = load_contracts(c_path)
    contracts["contract_id"] = pd.to_numeric(contracts["contract_id"], errors="coerce").astype("Int64")
    contracts["price"] = pd.to_numeric(contracts["price"], errors="coerce").fillna(0.0)
    contracts["start_location_id"] = pd.to_numeric(contracts["start_location_id"], errors="coerce").astype("Int64")

    c = contracts[
        (contracts["type"] == "item_exchange")
        & (contracts["price"] >= MIN_CONTRACT_PRICE)
        & (contracts["price"] <= MAX_CONTRACT_PRICE)
        & contracts["start_location_id"].notna()
    ].copy()
    now = pd.Timestamp.now(tz="UTC")
    if "date_expired" in c.columns:
        exp = pd.to_datetime(c["date_expired"], utc=True, errors="coerce")
        c = c[exp.isna() | (exp > now + pd.Timedelta(hours=MIN_HOURS_TO_EXPIRE))].copy()

    valid_ids = set(c["contract_id"].dropna().astype(int))
    ii = items[items["contract_id"].isin(valid_ids)].copy()
    ii["contract_id"] = pd.to_numeric(ii["contract_id"], errors="coerce").astype("Int64")
    ii["_included"] = truthy_series(ii["is_included"])
    ii["_bpc"] = truthy_series(ii["is_blueprint_copy"])
    ii["quantity"] = pd.to_numeric(ii["quantity"], errors="coerce").fillna(0).astype(int)
    ii["type_id"] = pd.to_numeric(ii["type_id"], errors="coerce").fillna(0).astype(int)

    # Item-exchange contracts requiring the buyer to provide items are not "buy and liquidate"
    # opportunities, and BPCs are handled by the dedicated BPC channels.
    requested_ids = set(ii.loc[~ii["_included"], "contract_id"].dropna().astype(int))
    bpc_ids = set(ii.loc[ii["_included"] & ii["_bpc"], "contract_id"].dropna().astype(int))
    usable_ids = valid_ids - requested_ids - bpc_ids
    inc = ii[ii["contract_id"].isin(usable_ids) & ii["_included"] & (ii["quantity"] > 0) & (ii["type_id"] > 0)].copy()
    grouped = {int(cid): aggregate_items(g) for cid, g in inc.groupby("contract_id", sort=False)}
    grouped = {cid: q for cid, q in grouped.items() if q}
    c = c[c["contract_id"].isin(grouped)].copy()
    if c.empty:
        empty_outputs()
        print("buy-only done: no usable contracts")
        return
    c_by_id = c.set_index("contract_id", drop=False)

    print(f"buy-only 2) Jita buy-depth valuation for {len(grouped)} contracts")
    orders = load_market_orders(m_path)
    _, buy_books = prepare_jita_books(orders)
    del orders

    # Broad pass is already buy-only. No sell price, average price or fallback price is allowed.
    prelim = []
    wanted_type_ids = set()
    for cid, itemq in grouped.items():
        cm = c_by_id.loc[cid]
        if isinstance(cm, pd.DataFrame):
            cm = cm.iloc[0]
        price = safe_num(cm.get("price"))
        value = buy_value(itemq, buy_books)
        gross = safe_num(value["jita_buy_gross"])
        tax = gross * SALES_TAX_RATE
        pre_location_profit = gross - tax - price
        if pre_location_profit < MIN_NET_PROFIT:
            continue
        prelim.append(
            {
                "contract_id": cid,
                "contract_price": price,
                "start_location_id": int(cm["start_location_id"]),
                "date_expired": cm.get("date_expired", ""),
                "title": cm.get("title", ""),
                "itemq": itemq,
                **value,
            }
        )
        wanted_type_ids.update(itemq)

    if not prelim:
        empty_outputs()
        print("buy-only done: no contract clears the buy-depth profit floor")
        return

    print(f"buy-only broad candidates={len(prelim)}; loading metadata for SKIN filter")
    type_objs = fetch_many_ref("types", wanted_type_ids)
    group_ids = {type_group_id(o) for o in type_objs.values()}
    group_ids.discard(None)
    group_objs = fetch_many_ref("groups", group_ids)

    skin_removed = 0
    skin_filtered = []
    for p in prelim:
        gross = safe_num(p["jita_buy_gross"])
        skin_value = sum(
            safe_num(r["buy_value"])
            for r in p["type_rows"]
            if is_skin_related(int(r["type_id"]), type_objs, group_objs)
        )
        share = skin_value / gross if gross > 0 else 0.0
        p["skin_buy_value"] = skin_value
        p["skin_value_share"] = share
        if share >= SKIN_MAJOR_SHARE:
            skin_removed += 1
            continue
        skin_filtered.append(p)
    prelim = skin_filtered
    print(f"buy-only SKIN-major removed={skin_removed}; remaining={len(prelim)}")

    if not prelim:
        empty_outputs()
        return

    print("buy-only 3) resolve executable locations")
    friendly_ids, own_alliance_id, own_alliance_name, own_alliance_ticker = current_friendly_alliances()
    sov_map = sovereignty_owners()
    loc_ids = sorted({p["start_location_id"] for p in prelim})
    structures = load_structures([x for x in loc_ids if x >= 1_000_000_000_000])
    locations = {}
    with ThreadPoolExecutor(max_workers=min(LOCATION_WORKERS, max(1, len(loc_ids)))) as ex:
        futs = {ex.submit(resolve_location, lid, structures, friendly_ids, sov_map): lid for lid in loc_ids}
        for fut in as_completed(futs):
            lid = futs[fut]
            try:
                locations[lid] = fut.result()
            except Exception:
                locations[lid] = None

    rows = []
    location_removed = 0
    player_structure_removed = 0
    for p in prelim:
        loc = locations.get(p["start_location_id"])
        if not loc or int(safe_num(loc.get("system_id"), 0)) <= 0:
            location_removed += 1
            continue
        if int(safe_num(loc.get("shortest_jumps_to_jita"), -1)) < 0:
            location_removed += 1
            continue
        # Unknown player structures are not treated as executable opportunities. Friendly sov/
        # explicitly friendly region structures may remain, because the configured character has
        # a plausible access path there.
        if bool(loc.get("is_player_structure")) and not bool(loc.get("friendly_sov")) and not bool(loc.get("friendly_region")):
            player_structure_removed += 1
            continue

        itemq = p["itemq"]
        total_m3 = sum(max(0.0, type_volume(type_objs.get(int(tid)))) * qty for tid, qty in itemq.items())
        haul = haul_reserve(total_m3, loc)
        gross = safe_num(p["jita_buy_gross"])
        sales_tax = gross * SALES_TAX_RATE
        net_value = gross - sales_tax - haul
        net_profit = net_value - p["contract_price"]
        invested = p["contract_price"] + haul
        roi = net_profit / invested if invested > 0 else 0.0

        stress_gross = safe_num(p["stress_jita_buy_gross"])
        stress_tax = stress_gross * SALES_TAX_RATE
        stress_profit = stress_gross - stress_tax - haul - p["contract_price"]

        if net_profit < MIN_NET_PROFIT or roi < MIN_NET_ROI:
            continue

        contrib = sorted(p["type_rows"], key=lambda x: safe_num(x.get("buy_value")), reverse=True)
        item_lines = [f"{name_en(type_objs.get(tid), str(tid))} x{qty}" for tid, qty in itemq.items()]
        contrib_lines = [
            f"{name_en(type_objs.get(int(r['type_id'])), str(r['type_id']))} x{int(r['quantity'])}≈{safe_num(r['buy_value'])/1e6:.1f}M"
            for r in contrib[:12]
        ]
        top1 = safe_num(contrib[0]["buy_value"]) / gross if gross > 0 and contrib else 0.0
        top3 = sum(safe_num(r["buy_value"]) for r in contrib[:3]) / gross if gross > 0 else 0.0

        row = {
            "deal_class": "A 即时买单套利",
            "valuation_basis": "JITA_BUY_DEPTH_ONLY",
            "risk_tier": loc.get("risk_tier", ""),
            "risk_rank": loc.get("risk_rank", 5),
            "deal_score": round(min(100.0, 45 + min(30, roi * 100) + min(25, net_profit / 10_000_000)), 1),
            "contract_id": p["contract_id"],
            "contract_price": p["contract_price"],
            "item_type_count": len(itemq),
            "item_total_units": sum(itemq.values()),
            "items": " | ".join(item_lines[:20]),
            "top_value_items": " | ".join(contrib_lines),
            "jita_buy_gross": gross,
            "sales_tax_if_instant": sales_tax,
            "instant_liquidation_net_value": net_value,
            "haul_reserve": haul,
            "instant_net_profit": net_profit,
            "instant_net_roi": roi,
            "stress_jita_buy_gross": stress_gross,
            "stress_net_profit": stress_profit,
            "buy_unit_coverage": safe_num(p["buy_unit_coverage"]),
            "buy_filled_units": int(p["buy_filled_units"]),
            "total_units": int(p["total_units"]),
            "top1_value_share": top1,
            "top3_value_share": top3,
            "skin_value_share": safe_num(p["skin_value_share"]),
            "total_m3": total_m3,
            # Compatibility columns: deliberately zeroed so no downstream path can silently
            # resurrect a Jita sell-price valuation.
            "jita_replacement_value": 0.0,
            "list_broker_fee": 0.0,
            "list_sales_tax": 0.0,
            "list_relist_reserve": 0.0,
            "list_net_profit_est": 0.0,
            "list_net_roi_est": 0.0,
            "priced_buy_types": sum(1 for r in p["type_rows"] if int(r["buy_filled"]) > 0),
            "fully_buy_types": sum(1 for r in p["type_rows"] if bool(r["buy_complete"])),
            "priced_sell_types": 0,
            "value_coverage": 1.0,
            # Multi-item mail compatibility; these are all the same buy-only executable metric.
            "chosen_estimated_value": net_value,
            "chosen_value_gap": net_profit,
            "chosen_discount": net_profit / net_value if net_value > 0 else 0.0,
            "chosen_roi": roi,
            "jita_sell_gross_raw": 0.0,
            "liquidity_adjusted_market_gross": 0.0,
            "market_net_value": 0.0,
            "contract_title": p.get("title", ""),
            "date_expired": p.get("date_expired", ""),
            "friendly_alliance_id": own_alliance_id,
            "friendly_alliance_name": own_alliance_name,
            "friendly_alliance_ticker": own_alliance_ticker,
            "eve_contract_url": f"https://eve-contract-opener.99617224.workers.dev/c/{p['contract_id']}",
            **loc,
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values(["instant_net_profit", "instant_net_roi", "stress_net_profit"], ascending=[False, False, False], inplace=True)
    LATEST.mkdir(parents=True, exist_ok=True)
    df.to_csv(SPOT_ALL, index=False)
    df.head(TOP).to_csv(SPOT_RESULT, index=False)

    multi = df[df["item_type_count"] >= 2].copy() if not df.empty else pd.DataFrame()
    if not multi.empty:
        multi.sort_values(["chosen_value_gap", "chosen_roi", "stress_net_profit"], ascending=[False, False, False], inplace=True)
    multi.to_csv(MULTI_ALL, index=False)
    multi.head(MULTI_TOP).to_csv(MULTI_RESULT, index=False)

    print(
        "buy-only done: "
        f"spot={len(df)} multi={len(multi)} skin_removed={skin_removed} "
        f"location_removed={location_removed} unknown_structure_removed={player_structure_removed}; "
        f"policy price<={MAX_CONTRACT_PRICE/1e9:.1f}B profit>={MIN_NET_PROFIT/1e6:.0f}M ROI>={MIN_NET_ROI:.0%}"
    )


if __name__ == "__main__":
    main()
