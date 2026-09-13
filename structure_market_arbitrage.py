from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path

import pandas as pd
import requests

from scanner_source import (
    MARKET_ORDERS_INDEX,
    DATA,
    LATEST,
    latest_file,
    download,
    load_market_orders,
    prepare_jita_books,
    fetch_many_ref,
    name_en,
    type_volume,
)
from contract_deal_scanner import SALES_TAX_RATE

STRUCTURE_ID = int(os.getenv("FOUR_H_STRUCTURE_ID", "1053970513596"))
WORKER_URL = os.getenv("EVE_MARKET_WORKER_URL", "https://eve-contract-opener.99617224.workers.dev").rstrip("/")
API_KEY = os.getenv("EVE_MARKET_API_KEY", "")
MIN_NET_PROFIT = float(os.getenv("FOUR_H_MIN_NET_PROFIT", "10000000"))
MIN_NET_ROI = float(os.getenv("FOUR_H_MIN_NET_ROI", "0.10"))
TOP = int(os.getenv("FOUR_H_TOP", "100"))
REQUEST_TIMEOUT = int(os.getenv("FOUR_H_REQUEST_TIMEOUT", "60"))

RESULT = LATEST / "four_h_to_jita_buy.csv"
REPORT = LATEST / "four_h_to_jita_buy.md"


def fetch_structure_page(page: int) -> dict:
    if not API_KEY:
        raise RuntimeError("Missing EVE_MARKET_API_KEY")
    r = requests.get(
        f"{WORKER_URL}/api/structure-market",
        params={"structure_id": STRUCTURE_ID, "page": int(page)},
        headers={"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"},
        timeout=REQUEST_TIMEOUT,
    )
    try:
        payload = r.json()
    except Exception:
        raise RuntimeError(f"Worker returned HTTP {r.status_code}: {r.text[:500]}")
    if r.status_code != 200 or not payload.get("ok"):
        if r.status_code == 403:
            raise RuntimeError(
                "4-H structure market access is not authorized. Re-authorize the EVE character at /auth "
                "with esi-markets.structure_markets.v1 and ensure the character can access the structure."
            )
        raise RuntimeError(f"Worker structure market error HTTP {r.status_code}: {payload}")
    return payload


def load_structure_sells() -> tuple[dict[int, list[dict]], int, str | None]:
    first = fetch_structure_page(1)
    pages = max(1, int(first.get("pages") or 1))
    all_orders = list(first.get("orders") or [])
    expires = first.get("expires")
    for page in range(2, pages + 1):
        data = fetch_structure_page(page)
        all_orders.extend(data.get("orders") or [])

    sells: dict[int, list[dict]] = defaultdict(list)
    for row in all_orders:
        if bool(row.get("is_buy_order")):
            continue
        try:
            tid = int(row["type_id"])
            price = float(row["price"])
            vol = int(row.get("volume_remain") or 0)
            min_vol = int(row.get("min_volume") or 1)
        except Exception:
            continue
        if tid <= 0 or price <= 0 or vol <= 0:
            continue
        sells[tid].append(
            {
                "price": price,
                "vol": vol,
                "min": max(1, min_vol),
                "order_id": int(row.get("order_id") or 0),
                "issued": row.get("issued") or "",
            }
        )
    for book in sells.values():
        book.sort(key=lambda x: (x["price"], x["order_id"]))
    return sells, len(all_orders), expires


def match_profitable(asks: list[dict], bids: list[dict]) -> dict | None:
    if not asks or not bids:
        return None
    ai = bi = 0
    ask_left = int(asks[0]["vol"])
    bid_left = int(bids[0]["vol"])
    qty = 0
    source_cost = 0.0
    jita_gross = 0.0
    first_ask = float(asks[0]["price"])
    first_bid = float(bids[0]["price"])
    worst_ask = first_ask
    worst_bid = first_bid
    source_order_ids: set[int] = set()
    jita_orders_used = 0

    while ai < len(asks) and bi < len(bids):
        ask = asks[ai]
        bid = bids[bi]
        ask_price = float(ask["price"])
        bid_price = float(bid["price"])
        net_bid = bid_price * (1.0 - SALES_TAX_RATE)
        unit_profit = net_bid - ask_price
        unit_roi = unit_profit / ask_price if ask_price > 0 else -1.0
        if unit_profit <= 0 or unit_roi < MIN_NET_ROI:
            break

        take = min(ask_left, bid_left)
        bid_min = max(1, int(bid.get("min", 1)))
        if take < bid_min:
            bi += 1
            if bi >= len(bids):
                break
            bid_left = int(bids[bi]["vol"])
            continue

        qty += take
        source_cost += ask_price * take
        jita_gross += bid_price * take
        worst_ask = ask_price
        worst_bid = bid_price
        source_order_ids.add(int(ask.get("order_id") or 0))
        jita_orders_used += 1

        ask_left -= take
        bid_left -= take
        if ask_left <= 0:
            ai += 1
            if ai < len(asks):
                ask_left = int(asks[ai]["vol"])
        if bid_left <= 0:
            bi += 1
            if bi < len(bids):
                bid_left = int(bids[bi]["vol"])

    if qty <= 0 or source_cost <= 0:
        return None
    tax = jita_gross * SALES_TAX_RATE
    net_revenue = jita_gross - tax
    net_profit = net_revenue - source_cost
    roi = net_profit / source_cost
    return {
        "quantity": qty,
        "source_cost": source_cost,
        "jita_buy_gross": jita_gross,
        "sales_tax": tax,
        "net_revenue": net_revenue,
        "net_profit": net_profit,
        "net_roi": roi,
        "four_h_best_sell": first_ask,
        "four_h_worst_matched_sell": worst_ask,
        "jita_best_buy": first_bid,
        "jita_worst_matched_buy": worst_bid,
        "source_orders_used": len(source_order_ids),
        "jita_orders_used": jita_orders_used,
    }


def fmt_isk(v: float) -> str:
    v = float(v)
    if abs(v) >= 1e9:
        return f"{v / 1e9:.2f}B"
    if abs(v) >= 1e6:
        return f"{v / 1e6:.2f}M"
    if abs(v) >= 1e3:
        return f"{v / 1e3:.1f}K"
    return f"{v:.0f}"


def main() -> None:
    LATEST.mkdir(parents=True, exist_ok=True)
    print(f"1) Reading live 4-H structure market {STRUCTURE_ID} via authenticated ESI proxy")
    sell_books, structure_order_count, structure_expires = load_structure_sells()
    print(f"   structure orders={structure_order_count:,}, sell types={len(sell_books):,}, expires={structure_expires}")

    print("2) Loading latest universe market-order snapshot and Jita 4-4 buy depth")
    market_url, market_modified = latest_file(MARKET_ORDERS_INDEX)
    market_path = DATA / Path(market_url).name
    if not market_path.exists():
        download(market_url, market_path)
    market_orders = load_market_orders(market_path)
    _, jita_buys = prepare_jita_books(market_orders)
    del market_orders
    print(f"   market snapshot={market_modified}")

    print("3) Matching 4-H asks directly into Jita buy-order depth")
    rows = []
    candidate_ids = []
    for tid, asks in sell_books.items():
        matched = match_profitable(asks, jita_buys.get(tid, []))
        if not matched:
            continue
        if matched["net_profit"] < MIN_NET_PROFIT or matched["net_roi"] < MIN_NET_ROI:
            continue
        rows.append({"type_id": tid, **matched})
        candidate_ids.append(tid)

    type_objs = fetch_many_ref("types", candidate_ids) if candidate_ids else {}
    for row in rows:
        obj = type_objs.get(int(row["type_id"]))
        row["item_name"] = name_en(obj, str(row["type_id"]))
        row["unit_volume_m3"] = type_volume(obj)
        total_m3 = row["unit_volume_m3"] * row["quantity"]
        row["total_volume_m3"] = total_m3
        row["profit_per_m3"] = row["net_profit"] / total_m3 if total_m3 > 0 else 0.0

    rows.sort(key=lambda r: (r["net_profit"], r["net_roi"], r["profit_per_m3"]), reverse=True)
    rows = rows[:TOP]
    df = pd.DataFrame(rows)
    df.to_csv(RESULT, index=False)

    lines = [
        "# 4-HWWF → Jita 4-4 direct-buy arbitrage",
        "",
        f"- Structure ID: `{STRUCTURE_ID}`",
        f"- 4-H ESI cache expiry: `{structure_expires}`",
        f"- Jita market snapshot: `{market_modified}`",
        f"- Sales tax used: `{SALES_TAX_RATE:.4%}`",
        f"- Filters: net profit ≥ {fmt_isk(MIN_NET_PROFIT)} ISK, ROI ≥ {MIN_NET_ROI:.1%}",
        "- Revenue assumes immediate liquidation into visible Jita 4-4 buy-order depth; no Jita sell orders are used.",
        "",
    ]
    if not rows:
        lines.append("No opportunity passed the current filters.")
    else:
        lines.extend([
            "| # | Item | Qty | 4-H best sell | Jita best buy | Worst matched bid | Net profit | ROI | Profit/m³ |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for i, r in enumerate(rows, 1):
            lines.append(
                f"| {i} | {r['item_name']} | {r['quantity']:,} | {fmt_isk(r['four_h_best_sell'])} | "
                f"{fmt_isk(r['jita_best_buy'])} | {fmt_isk(r['jita_worst_matched_buy'])} | "
                f"{fmt_isk(r['net_profit'])} | {r['net_roi']:.1%} | {fmt_isk(r['profit_per_m3'])} |"
            )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"4) opportunities={len(rows)}")
    if rows:
        for i, r in enumerate(rows[:20], 1):
            print(
                f"{i:02d}. {r['item_name']} | qty={r['quantity']} | 4-H={fmt_isk(r['four_h_best_sell'])} | "
                f"JitaBuy={fmt_isk(r['jita_best_buy'])} | net={fmt_isk(r['net_profit'])} | ROI={r['net_roi']:.1%}"
            )
    print(f"wrote {RESULT} and {REPORT}")


if __name__ == "__main__":
    main()
