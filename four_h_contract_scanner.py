from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path

import pandas as pd
import requests

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
    type_volume,
)
from contract_deal_scanner import SALES_TAX_RATE

STRUCTURE_ID = int(os.getenv("FOUR_H_STRUCTURE_ID", "1053970513596"))
WORKER_URL = os.getenv("EVE_MARKET_WORKER_URL", "https://eve-contract-opener.99617224.workers.dev").rstrip("/")
API_KEY = os.getenv("EVE_MARKET_API_KEY", "")
MIN_PRICE = float(os.getenv("FOUR_H_CONTRACT_MIN_PRICE", "1000000"))
MIN_NET_PROFIT = float(os.getenv("FOUR_H_CONTRACT_MIN_NET_PROFIT", "5000000"))
MIN_NET_ROI = float(os.getenv("FOUR_H_CONTRACT_MIN_NET_ROI", "0.05"))
TOP = int(os.getenv("FOUR_H_CONTRACT_TOP", "100"))

RESULT = LATEST / "four_h_contract_bargains.csv"
REPORT = LATEST / "four_h_contract_bargains.md"


def fetch_structure_orders():
    if not API_KEY:
        raise RuntimeError("Missing EVE_MARKET_API_KEY")
    page = 1
    raw = []
    pages = 1
    while page <= pages:
        r = requests.get(
            f"{WORKER_URL}/api/structure-market",
            params={"structure_id": STRUCTURE_ID, "page": page},
            headers={"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"},
            timeout=60,
        )
        try:
            data = r.json()
        except Exception:
            raise RuntimeError(f"Structure market HTTP {r.status_code}: {r.text[:500]}")
        if r.status_code != 200 or not data.get("ok"):
            raise RuntimeError(f"Structure market error HTTP {r.status_code}: {data}")
        pages = max(1, int(data.get("pages") or 1))
        raw.extend(data.get("orders") or [])
        page += 1
    return raw


def build_books(rows):
    sells = defaultdict(list)
    buys = defaultdict(list)
    for row in rows:
        try:
            tid = int(row["type_id"])
            price = float(row["price"])
            vol = int(row.get("volume_remain") or 0)
            minv = max(1, int(row.get("min_volume") or 1))
        except Exception:
            continue
        if tid <= 0 or price <= 0 or vol <= 0:
            continue
        rec = {"price": price, "vol": vol, "min": minv}
        if bool(row.get("is_buy_order")):
            buys[tid].append(rec)
        else:
            sells[tid].append(rec)
    for book in buys.values():
        book.sort(key=lambda x: x["price"], reverse=True)
    for book in sells.values():
        book.sort(key=lambda x: x["price"])
    return sells, buys


def aggregate_items(df):
    out = defaultdict(int)
    for r in df.itertuples(index=False):
        try:
            tid = int(r.type_id)
            qty = int(r.quantity)
        except Exception:
            continue
        if tid > 0 and qty > 0:
            out[tid] += qty
    return dict(out)


def liquidate(itemq, books):
    gross = 0.0
    details = []
    complete = True
    for tid, qty in itemq.items():
        f = fill_book(books.get(int(tid), []), int(qty))
        if not f.complete:
            complete = False
        gross += f.value
        details.append((f.value, tid, qty, f.avg_price, f.complete))
    return complete, gross, sorted(details, reverse=True)


def replacement(itemq, sell_books):
    gross = 0.0
    complete = True
    for tid, qty in itemq.items():
        f = fill_book(sell_books.get(int(tid), []), int(qty))
        if not f.complete:
            complete = False
        gross += f.value
    return complete, gross


def fmt_isk(v):
    v = float(v or 0)
    if abs(v) >= 1e9:
        return f"{v/1e9:.2f}B"
    if abs(v) >= 1e6:
        return f"{v/1e6:.2f}M"
    if abs(v) >= 1e3:
        return f"{v/1e3:.1f}K"
    return f"{v:.0f}"


def main():
    LATEST.mkdir(parents=True, exist_ok=True)

    print("1) latest public contracts + Jita market")
    c_url, c_modified = latest_file(PUBLIC_CONTRACTS_INDEX)
    m_url, m_modified = latest_file(MARKET_ORDERS_INDEX)
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
        & (contracts["start_location_id"] == STRUCTURE_ID)
        & (contracts["price"] >= MIN_PRICE)
    ].copy()

    now = pd.Timestamp.now(tz="UTC")
    if "date_expired" in c.columns:
        exp = pd.to_datetime(c["date_expired"], utc=True, errors="coerce")
        c = c[exp.isna() | (exp > now + pd.Timedelta(minutes=10))].copy()

    valid_ids = set(c["contract_id"].dropna().astype(int))
    ii = items[items["contract_id"].isin(valid_ids)].copy()
    ii["contract_id"] = pd.to_numeric(ii["contract_id"], errors="coerce").astype("Int64")
    ii["_included"] = truthy_series(ii["is_included"])
    ii["_bpc"] = truthy_series(ii["is_blueprint_copy"])
    ii["quantity"] = pd.to_numeric(ii["quantity"], errors="coerce").fillna(0).astype(int)
    ii["type_id"] = pd.to_numeric(ii["type_id"], errors="coerce").fillna(0).astype(int)

    requested_ids = set(ii.loc[~ii["_included"], "contract_id"].dropna().astype(int))
    bpc_ids = set(ii.loc[ii["_included"] & ii["_bpc"], "contract_id"].dropna().astype(int))
    usable_ids = valid_ids - requested_ids - bpc_ids
    c = c[c["contract_id"].isin(usable_ids)].copy()
    inc = ii[ii["contract_id"].isin(usable_ids) & ii["_included"] & (ii["quantity"] > 0) & (ii["type_id"] > 0)].copy()
    grouped = {int(cid): aggregate_items(g) for cid, g in inc.groupby("contract_id", sort=False)}

    print(f"   4-H active item-exchange contracts={len(c):,}; excluded requested/BPC={len(valid_ids)-len(usable_ids):,}")

    print("2) current 4-H structure market + Jita order books")
    structure_rows = fetch_structure_orders()
    four_h_sells, four_h_buys = build_books(structure_rows)
    market = load_market_orders(m_path)
    jita_sells, jita_buys = prepare_jita_books(market)
    del market
    print(f"   4-H market orders={len(structure_rows):,}")

    c_by_id = c.set_index("contract_id", drop=False)
    rows = []
    all_type_ids = set()
    raw_detail = {}
    for cid, itemq in grouped.items():
        if cid not in c_by_id.index or not itemq:
            continue
        cr = c_by_id.loc[cid]
        if isinstance(cr, pd.DataFrame):
            cr = cr.iloc[0]
        price = float(cr.get("price") or 0)
        if price <= 0:
            continue

        local_complete, local_gross, local_details = liquidate(itemq, four_h_buys)
        jita_complete, jita_gross, jita_details = liquidate(itemq, jita_buys)
        local_sell_complete, local_repl = replacement(itemq, four_h_sells)
        jita_sell_complete, jita_repl = replacement(itemq, jita_sells)

        local_net = local_gross * (1.0 - SALES_TAX_RATE) - price if local_complete else float("-inf")
        jita_net = jita_gross * (1.0 - SALES_TAX_RATE) - price if jita_complete else float("-inf")
        local_roi = local_net / price if local_complete else float("-inf")
        jita_roi = jita_net / price if jita_complete else float("-inf")
        best_net = max(local_net, jita_net)
        best_roi = max(local_roi, jita_roi)
        if best_net < MIN_NET_PROFIT or best_roi < MIN_NET_ROI:
            continue

        route = "4-H local buy" if local_net >= jita_net else "Jita 4-4 buy"
        details = local_details if route == "4-H local buy" else jita_details
        all_type_ids.update(itemq)
        raw_detail[cid] = details
        rows.append({
            "contract_id": cid,
            "title": str(cr.get("title") or ""),
            "price": price,
            "item_types": len(itemq),
            "local_buy_complete": local_complete,
            "local_buy_gross": local_gross,
            "local_net_profit": local_net if local_complete else None,
            "local_roi": local_roi if local_complete else None,
            "jita_buy_complete": jita_complete,
            "jita_buy_gross": jita_gross,
            "jita_net_profit_before_haul": jita_net if jita_complete else None,
            "jita_roi_before_haul": jita_roi if jita_complete else None,
            "four_h_sell_replacement": local_repl if local_sell_complete else None,
            "jita_sell_replacement": jita_repl if jita_sell_complete else None,
            "best_route": route,
            "best_net_profit": best_net,
            "best_roi": best_roi,
        })

    objs = fetch_many_ref("types", all_type_ids) if all_type_ids else {}
    itemqs = grouped
    for row in rows:
        cid = int(row["contract_id"])
        itemq = itemqs[cid]
        total_m3 = 0.0
        for tid, qty in itemq.items():
            total_m3 += type_volume(objs.get(tid)) * qty
        row["packaged_volume_m3"] = total_m3

        top_names = []
        for value, tid, qty, avg, complete in raw_detail.get(cid, [])[:5]:
            nm = name_en(objs.get(int(tid)), str(tid))
            top_names.append(f"{nm} x{qty} @ {fmt_isk(avg)}")
        row["top_items"] = "; ".join(top_names)

    rows.sort(key=lambda r: (r["best_net_profit"], r["best_roi"]), reverse=True)
    rows = rows[:TOP]
    pd.DataFrame(rows).to_csv(RESULT, index=False)

    lines = [
        "# 4-HWWF contract bargain scan",
        "",
        f"- Structure ID: `{STRUCTURE_ID}`",
        f"- Public contracts snapshot: `{c_modified}`",
        f"- Jita market snapshot: `{m_modified}`",
        f"- Active 4-H item-exchange contracts scanned: `{len(c)}`",
        f"- 4-H market orders read: `{len(structure_rows)}`",
        f"- Filters: best executable net profit >= {fmt_isk(MIN_NET_PROFIT)}, ROI >= {MIN_NET_ROI:.1%}`",
        f"- Sales tax: `{SALES_TAX_RATE:.3%}`",
        "- BPC contracts and contracts asking for items are excluded from this pass.",
        "- Jita route profit is before hauling cost/risk; 4-H local route needs no hauling.",
        "",
    ]
    if not rows:
        lines.append("No executable bargain passed the filters.")
    else:
        lines += [
            "| # | Contract | Title | Price | Best route | Net profit | ROI | Volume m3 | Top items |",
            "|---:|---:|---|---:|---|---:|---:|---:|---|",
        ]
        for i, r in enumerate(rows, 1):
            lines.append(
                f"| {i} | {r['contract_id']} | {r['title'].replace('|','/')} | {fmt_isk(r['price'])} | "
                f"{r['best_route']} | {fmt_isk(r['best_net_profit'])} | {r['best_roi']:.1%} | "
                f"{r['packaged_volume_m3']:.0f} | {r['top_items'].replace('|','/')} |"
            )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"3) bargains={len(rows)}")
    for i, r in enumerate(rows[:30], 1):
        print(
            f"{i:02d}. contract={r['contract_id']} | {r['title']} | price={fmt_isk(r['price'])} | "
            f"route={r['best_route']} | net={fmt_isk(r['best_net_profit'])} | ROI={r['best_roi']:.1%} | "
            f"m3={r['packaged_volume_m3']:.0f} | {r['top_items']}"
        )
    print(f"wrote {RESULT} and {REPORT}")


if __name__ == "__main__":
    from four_h_contract_scanner_v2 import main as v2_main
    v2_main()
