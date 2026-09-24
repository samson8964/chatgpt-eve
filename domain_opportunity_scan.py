from __future__ import annotations

import math
import os
from pathlib import Path

import pandas as pd

from scanner_source import (
    DATA,
    JITA_SYSTEM,
    MARKET_ORDERS_INDEX,
    PUBLIC_CONTRACTS_INDEX,
    download,
    fetch_many_ref,
    fill_book,
    latest_file,
    load_contracts,
    load_market_orders,
    name_en,
    prepare_jita_books,
    route_jumps,
    station_info,
    system_info,
    truthy_series,
    type_volume,
)
from contract_deal_scanner import SALES_TAX_RATE

DOMAIN_REGION = 10000043
JITA_44 = 60003760

CONTRACT_MIN_PRICE = float(os.getenv("DOMAIN_CONTRACT_MIN_PRICE", "1000000"))
CONTRACT_MAX_PRICE = float(os.getenv("DOMAIN_CONTRACT_MAX_PRICE", "5000000000"))
CONTRACT_MIN_PROFIT = float(os.getenv("DOMAIN_CONTRACT_MIN_PROFIT", "30000000"))
CONTRACT_MIN_ROI = float(os.getenv("DOMAIN_CONTRACT_MIN_ROI", "0.10"))

MARKET_MIN_PROFIT = float(os.getenv("DOMAIN_MARKET_MIN_PROFIT", "10000000"))
MARKET_MIN_ROI = float(os.getenv("DOMAIN_MARKET_MIN_ROI", "0.10"))

HAUL_BASE = float(os.getenv("DOMAIN_HAUL_BASE_ISK", "2000000"))
HAUL_PER_M3_JUMP = float(os.getenv("DOMAIN_HAUL_ISK_PER_M3_JUMP", "200"))
MIN_HOURS_TO_EXPIRE = float(os.getenv("DOMAIN_MIN_HOURS_TO_EXPIRE", "0.5"))

OUT = Path("results/domain/latest")
OUT.mkdir(parents=True, exist_ok=True)


def safe_float(x, default=0.0):
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def truthy(v):
    if isinstance(v, bool):
        return v
    return str(v or "").strip().lower() in {"1", "true", "t", "yes", "y"}


def stress_book(book):
    if not book:
        return []
    best = float(book[0]["price"])
    return [x for x in book if float(x["price"]) != best]


def location_details(system_id: int, station_id: int):
    try:
        sy = system_info(int(system_id))
        sec = float(sy.get("security_status", 0.0))
        if sec < 0.5:
            return None
        jumps = route_jumps(int(system_id), JITA_SYSTEM, "secure")
        if jumps < 0:
            return None
        st = station_info(int(station_id))
        return {
            "system_name": sy.get("name", str(system_id)),
            "security": round(sec, 3),
            "secure_jumps_to_jita": int(jumps),
            "station_name": st.get("name", str(station_id)),
        }
    except Exception:
        return None


def haul_cost(volume_m3: float, jumps: int):
    if jumps <= 0:
        return 0.0
    return HAUL_BASE + max(0.0, volume_m3) * jumps * HAUL_PER_M3_JUMP


def aggregate_contract_items(df: pd.DataFrame):
    out = {}
    for cid, g in df.groupby("contract_id", sort=False):
        q = {}
        for r in g.itertuples(index=False):
            tid = int(r.type_id)
            qty = int(r.quantity)
            if tid > 0 and qty > 0:
                q[tid] = q.get(tid, 0) + qty
        if q:
            out[int(cid)] = q
    return out


def contract_scan(contracts, items, jita_buys):
    c = contracts.copy()
    c["contract_id"] = pd.to_numeric(c["contract_id"], errors="coerce").astype("Int64")
    c["price"] = pd.to_numeric(c["price"], errors="coerce").fillna(0.0)
    c["start_location_id"] = pd.to_numeric(c["start_location_id"], errors="coerce").astype("Int64")
    c["region_id"] = pd.to_numeric(c["region_id"], errors="coerce").fillna(0).astype(int)
    if "system_id" in c.columns:
        c["system_id"] = pd.to_numeric(c["system_id"], errors="coerce").fillna(0).astype(int)
    else:
        c["system_id"] = 0

    c = c[
        (c["region_id"] == DOMAIN_REGION)
        & (c["type"] == "item_exchange")
        & (c["price"] >= CONTRACT_MIN_PRICE)
        & (c["price"] <= CONTRACT_MAX_PRICE)
        & c["start_location_id"].notna()
        & (c["start_location_id"] < 1_000_000_000_000)
    ].copy()

    now = pd.Timestamp.now(tz="UTC")
    if "date_expired" in c.columns:
        exp = pd.to_datetime(c["date_expired"], utc=True, errors="coerce")
        c = c[exp.isna() | (exp > now + pd.Timedelta(hours=MIN_HOURS_TO_EXPIRE))].copy()

    if c.empty:
        return pd.DataFrame(), pd.DataFrame()

    ids = set(c["contract_id"].dropna().astype(int))
    ii = items[items["contract_id"].isin(ids)].copy()
    ii["contract_id"] = pd.to_numeric(ii["contract_id"], errors="coerce").astype("Int64")
    ii["quantity"] = pd.to_numeric(ii["quantity"], errors="coerce").fillna(0).astype(int)
    ii["type_id"] = pd.to_numeric(ii["type_id"], errors="coerce").fillna(0).astype(int)
    ii["_included"] = truthy_series(ii["is_included"])
    if "is_blueprint_copy" in ii.columns:
        ii["_bpc"] = truthy_series(ii["is_blueprint_copy"])
    else:
        ii["_bpc"] = False

    requested = set(ii.loc[~ii["_included"], "contract_id"].dropna().astype(int))
    bpc_contracts = set(ii.loc[ii["_included"] & ii["_bpc"], "contract_id"].dropna().astype(int))
    usable = ids - requested - bpc_contracts

    inc = ii[ii["contract_id"].isin(usable) & ii["_included"] & (ii["quantity"] > 0) & (ii["type_id"] > 0)].copy()
    grouped = aggregate_contract_items(inc)
    if not grouped:
        return pd.DataFrame(), pd.DataFrame()

    cidx = c[c["contract_id"].isin(grouped)].set_index("contract_id", drop=False)
    prelim = []
    candidate_tids = set()
    for cid, itemq in grouped.items():
        if cid not in cidx.index:
            continue
        cm = cidx.loc[cid]
        if isinstance(cm, pd.DataFrame):
            cm = cm.iloc[0]
        price = safe_float(cm.get("price"))
        gross = 0.0
        stress_gross = 0.0
        complete = True
        stress_complete = True
        for tid, qty in itemq.items():
            f = fill_book(jita_buys.get(int(tid), []), int(qty))
            sf = fill_book(stress_book(jita_buys.get(int(tid), [])), int(qty))
            gross += f.value
            stress_gross += sf.value
            complete = complete and f.complete
            stress_complete = stress_complete and sf.complete
        if not complete:
            continue
        raw_profit = gross * (1 - SALES_TAX_RATE) - price
        raw_roi = raw_profit / price if price > 0 else 0.0
        if raw_profit < max(10_000_000, CONTRACT_MIN_PROFIT * 0.35) or raw_roi < 0.04:
            continue
        prelim.append((cid, cm, itemq, gross, stress_gross, stress_complete))
        candidate_tids.update(itemq.keys())

    types = fetch_many_ref("types", candidate_tids)
    rows = []
    near = []
    loc_cache = {}
    for cid, cm, itemq, gross, stress_gross, stress_complete in prelim:
        sid = int(cm.get("system_id") or 0)
        lid = int(cm.get("start_location_id"))
        key = (sid, lid)
        if key not in loc_cache:
            loc_cache[key] = location_details(sid, lid) if sid > 0 else None
        loc = loc_cache[key]
        if not loc:
            continue

        total_m3 = sum(max(0.0, type_volume(types.get(int(tid)))) * int(qty) for tid, qty in itemq.items())
        haul = haul_cost(total_m3, loc["secure_jumps_to_jita"])
        price = safe_float(cm.get("price"))
        net = gross * (1 - SALES_TAX_RATE) - price - haul
        invested = price + haul
        roi = net / invested if invested > 0 else 0.0
        stress_net = stress_gross * (1 - SALES_TAX_RATE) - price - haul if stress_complete else -1e30

        item_lines = [f"{name_en(types.get(int(tid)), str(tid))} x{qty}" for tid, qty in itemq.items()]
        row = {
            "channel": "DOMAIN_CONTRACT_TO_JITA_BUY",
            "contract_id": int(cid),
            "contract_price": price,
            "jita_buy_gross": gross,
            "sales_tax": gross * SALES_TAX_RATE,
            "haul_reserve": haul,
            "net_profit": net,
            "net_roi": roi,
            "stress_net_profit": stress_net,
            "stress_complete": stress_complete,
            "item_type_count": len(itemq),
            "item_total_units": sum(itemq.values()),
            "items": " | ".join(item_lines[:30]),
            "total_m3": total_m3,
            "date_expired": cm.get("date_expired", ""),
            "contract_title": cm.get("title", ""),
            "start_location_id": lid,
            "system_id": sid,
            "eve_contract_url": f"https://eve-contract-opener.99617224.workers.dev/c/{int(cid)}",
            **loc,
        }
        near.append(row)
        if net >= CONTRACT_MIN_PROFIT and roi >= CONTRACT_MIN_ROI and stress_net > 0:
            rows.append(row)

    df = pd.DataFrame(rows)
    nr = pd.DataFrame(near)
    if not df.empty:
        df.sort_values(["net_profit", "net_roi"], ascending=[False, False], inplace=True)
    if not nr.empty:
        nr.sort_values(["net_profit", "net_roi"], ascending=[False, False], inplace=True)
    return df, nr.head(100)


def market_scan(orders, jita_buys):
    o = orders.copy()
    o["region_id"] = pd.to_numeric(o["region_id"], errors="coerce").fillna(0).astype(int)
    loc_col = "location_id" if "location_id" in o.columns else "station_id"
    o[loc_col] = pd.to_numeric(o[loc_col], errors="coerce").fillna(0).astype("int64")
    o["system_id"] = pd.to_numeric(o["system_id"], errors="coerce").fillna(0).astype(int)
    o["type_id"] = pd.to_numeric(o["type_id"], errors="coerce").fillna(0).astype(int)
    o["price"] = pd.to_numeric(o["price"], errors="coerce").fillna(0.0)
    o["volume_remain"] = pd.to_numeric(o["volume_remain"], errors="coerce").fillna(0).astype(int)
    b = truthy_series(o["is_buy_order"])

    sells = o[
        (o["region_id"] == DOMAIN_REGION)
        & (~b)
        & (o[loc_col] > 0)
        & (o[loc_col] < 1_000_000_000_000)
        & (o["volume_remain"] > 0)
        & (o["price"] > 0)
    ].copy()

    prelim = []
    tids = set()
    for r in sells.itertuples(index=False):
        tid = int(r.type_id)
        book = jita_buys.get(tid, [])
        if not book:
            continue
        best = float(book[0]["price"])
        source = float(r.price)
        # enough raw edge to survive tax/haul and the 10% ROI rule
        if best * (1 - SALES_TAX_RATE) <= source * 1.08:
            continue
        qty_req = int(r.volume_remain)
        f = fill_book(book, qty_req)
        qty = int(f.filled)
        if qty <= 0:
            continue
        raw_profit = f.value * (1 - SALES_TAX_RATE) - source * qty
        if raw_profit < MARKET_MIN_PROFIT * 0.45:
            continue
        prelim.append({
            "type_id": tid,
            "location_id": int(getattr(r, loc_col)),
            "system_id": int(r.system_id),
            "source_price": source,
            "source_available": qty_req,
            "qty": qty,
            "jita_gross": f.value,
            "jita_complete_for_source_order": bool(f.complete),
        })
        tids.add(tid)

    types = fetch_many_ref("types", tids)
    rows = []
    loc_cache = {}
    for p in prelim:
        key = (p["system_id"], p["location_id"])
        if key not in loc_cache:
            loc_cache[key] = location_details(p["system_id"], p["location_id"])
        loc = loc_cache[key]
        if not loc:
            continue

        unit_m3 = max(0.0, type_volume(types.get(p["type_id"])))
        total_m3 = unit_m3 * p["qty"]
        haul = haul_cost(total_m3, loc["secure_jumps_to_jita"])
        cost = p["source_price"] * p["qty"]
        revenue = p["jita_gross"] * (1 - SALES_TAX_RATE)
        net = revenue - cost - haul
        invested = cost + haul
        roi = net / invested if invested > 0 else 0.0

        sf = fill_book(stress_book(jita_buys.get(p["type_id"], [])), p["qty"])
        stress_net = (
            sf.value * (1 - SALES_TAX_RATE) - cost - haul
            if sf.complete else -1e30
        )

        if net < MARKET_MIN_PROFIT or roi < MARKET_MIN_ROI or stress_net <= 0:
            continue
        rows.append({
            "channel": "DOMAIN_MARKET_SELL_TO_JITA_BUY",
            "type_id": p["type_id"],
            "item": name_en(types.get(p["type_id"]), str(p["type_id"])),
            "buy_qty": p["qty"],
            "source_unit_price": p["source_price"],
            "source_available": p["source_available"],
            "source_cost": cost,
            "jita_buy_gross": p["jita_gross"],
            "sales_tax": p["jita_gross"] * SALES_TAX_RATE,
            "haul_reserve": haul,
            "net_profit": net,
            "net_roi": roi,
            "stress_net_profit": stress_net,
            "total_m3": total_m3,
            "location_id": p["location_id"],
            "system_id": p["system_id"],
            **loc,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values(["net_profit", "net_roi"], ascending=[False, False], inplace=True)
        # Avoid duplicate rows when identical cheap orders exist at one station.
        df.drop_duplicates(subset=["type_id", "location_id", "source_unit_price", "buy_qty"], inplace=True)
    return df


def main():
    c_url, c_modified = latest_file(PUBLIC_CONTRACTS_INDEX)
    m_url, m_modified = latest_file(MARKET_ORDERS_INDEX)
    c_path = DATA / Path(c_url).name
    m_path = DATA / Path(m_url).name
    if not c_path.exists():
        download(c_url, c_path)
    if not m_path.exists():
        download(m_url, m_path)

    contracts, items = load_contracts(c_path)
    orders = load_market_orders(m_path)
    _, jita_buys = prepare_jita_books(orders)

    contract_df, near_df = contract_scan(contracts, items, jita_buys)
    market_df = market_scan(orders, jita_buys)

    contract_df.to_csv(OUT / "domain_contract_opportunities.csv", index=False)
    near_df.to_csv(OUT / "domain_contract_research_top100.csv", index=False)
    market_df.to_csv(OUT / "domain_market_opportunities.csv", index=False)

    lines = [
        "# Domain / 多美星域捡漏扫描",
        "",
        f"- Contracts snapshot: {c_modified}",
        f"- Market snapshot: {m_modified}",
        f"- Sales tax assumption: {SALES_TAX_RATE:.3%}",
        f"- Contract production threshold: net profit >= {CONTRACT_MIN_PROFIT/1e6:.0f}M, ROI >= {CONTRACT_MIN_ROI:.0%}, stress profit > 0",
        f"- Market production threshold: net profit >= {MARKET_MIN_PROFIT/1e6:.0f}M, ROI >= {MARKET_MIN_ROI:.0%}, stress profit > 0",
        "- Scope: Domain NPC stations with a secure high-sec route to Jita; player structures, BPC contracts and barter contracts are excluded from this fast scan.",
        "",
        f"## Contract opportunities: {len(contract_df)}",
    ]
    if contract_df.empty:
        lines.append("No production-grade contract opportunities.")
    else:
        for _, r in contract_df.head(20).iterrows():
            lines.append(
                f"- #{int(r.contract_id)} | {r.net_profit/1e6:.1f}M | ROI {r.net_roi:.1%} | "
                f"{r.station_name} | {r.items[:180]}"
            )

    lines += ["", f"## Market opportunities: {len(market_df)}"]
    if market_df.empty:
        lines.append("No production-grade instant Domain sell -> Jita buy opportunities.")
    else:
        for _, r in market_df.head(20).iterrows():
            lines.append(
                f"- {r.item} x{int(r.buy_qty)} | {r.net_profit/1e6:.1f}M | ROI {r.net_roi:.1%} | "
                f"{r.station_name} | source {r.source_unit_price/1e6:.3f}M"
            )

    if not near_df.empty:
        lines += ["", "## Contract research top 10 (may be below production threshold)"]
        for _, r in near_df.head(10).iterrows():
            lines.append(
                f"- #{int(r.contract_id)} | {r.net_profit/1e6:.1f}M | ROI {r.net_roi:.1%} | "
                f"stress {r.stress_net_profit/1e6:.1f}M | {r.station_name} | {r.items[:180]}"
            )

    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
