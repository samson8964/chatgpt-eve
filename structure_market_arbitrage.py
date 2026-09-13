from __future__ import annotations

import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    truthy_series,
)
from contract_deal_scanner import SALES_TAX_RATE

STRUCTURE_ID = int(os.getenv("FOUR_H_STRUCTURE_ID", "1053970513596"))
MIN_NET_PROFIT = float(os.getenv("FOUR_H_MIN_NET_PROFIT", "10000000"))
MIN_NET_ROI = float(os.getenv("FOUR_H_MIN_NET_ROI", "0.10"))
JITA_SEED_MIN_BID = float(os.getenv("FOUR_H_JITA_SEED_MIN_BID", "5000000"))
TYCOON_WORKERS = int(os.getenv("FOUR_H_TYCOON_WORKERS", "12"))
TOP = int(os.getenv("FOUR_H_TOP", "100"))

TYCOON_ORDERS = "https://evetycoon.com/api/v1/market/orders/{type_id}"
UA = "chatgpt-eve-4h-jita-arbitrage/1.0"

RESULT = LATEST / "four_h_to_jita_buy.csv"
REPORT = LATEST / "four_h_to_jita_buy.md"


def four_h_visible_type_ids(orders: pd.DataFrame) -> set[int]:
    """Regional ESI exposes player-structure buy orders; use their type IDs as local-market seeds."""
    loc_col = "location_id" if "location_id" in orders.columns else "station_id"
    loc = pd.to_numeric(orders[loc_col], errors="coerce")
    frame = orders.loc[loc.eq(STRUCTURE_ID), "type_id"]
    return {int(x) for x in pd.to_numeric(frame, errors="coerce").dropna().astype(int).tolist() if int(x) > 0}


def fetch_tycoon_type(type_id: int) -> tuple[int, list[dict], str | None]:
    last_error = None
    for attempt in range(3):
        try:
            r = requests.get(
                TYCOON_ORDERS.format(type_id=int(type_id)),
                params={"locationId": STRUCTURE_ID},
                headers={"User-Agent": UA, "Accept": "application/json"},
                timeout=25,
            )
            if r.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code != 200:
                return int(type_id), [], f"HTTP {r.status_code}"
            payload = r.json()
            raw_orders = payload.get("orders") if isinstance(payload, dict) else []
            sells = []
            for row in raw_orders or []:
                try:
                    if int(row.get("locationId") or 0) != STRUCTURE_ID:
                        continue
                    if bool(row.get("isBuyOrder")):
                        continue
                    price = float(row.get("price") or 0)
                    vol = int(row.get("volumeRemain") or 0)
                    if price <= 0 or vol <= 0:
                        continue
                    sells.append({
                        "price": price,
                        "vol": vol,
                        "min": max(1, int(row.get("minVolume") or 1)),
                        "order_id": int(row.get("orderId") or 0),
                        "issued": str(row.get("issued") or ""),
                    })
                except Exception:
                    continue
            sells.sort(key=lambda x: (x["price"], x["order_id"]))
            return int(type_id), sells, None
        except Exception as e:
            last_error = str(e)
            if attempt < 2:
                time.sleep(0.4 * (attempt + 1))
    return int(type_id), [], last_error or "request_failed"


def load_structure_sells_tycoon(candidate_ids: set[int]) -> tuple[dict[int, list[dict]], int, int]:
    sells: dict[int, list[dict]] = {}
    errors = 0
    checked = 0
    with ThreadPoolExecutor(max_workers=TYCOON_WORKERS) as ex:
        futs = {ex.submit(fetch_tycoon_type, tid): tid for tid in sorted(candidate_ids)}
        for fut in as_completed(futs):
            checked += 1
            try:
                tid, book, err = fut.result()
            except Exception:
                errors += 1
                continue
            if err:
                errors += 1
            if book:
                sells[tid] = book
            if checked % 250 == 0:
                print(f"   EVE Tycoon checked {checked:,}/{len(candidate_ids):,}; sell types found={len(sells):,}; errors={errors:,}")
    return sells, checked, errors


def match_profitable(asks: list[dict], bids: list[dict]) -> dict | None:
    """Match cheapest 4-H asks into highest Jita 4-4 bids while each marginal fill clears ROI floor."""
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
    bid_indexes_used: set[int] = set()

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
        bid_indexes_used.add(bi)

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
        "jita_orders_used": len(bid_indexes_used),
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
    print("1) Loading latest EVERef universe market-order snapshot for Jita buy depth")
    market_url, market_modified = latest_file(MARKET_ORDERS_INDEX)
    market_path = DATA / Path(market_url).name
    if not market_path.exists():
        download(market_url, market_path)
    market_orders = load_market_orders(market_path)
    _, jita_buys = prepare_jita_books(market_orders)

    local_seed_ids = four_h_visible_type_ids(market_orders)
    high_value_jita_ids = {
        int(tid) for tid, book in jita_buys.items()
        if book and float(book[0].get("price", 0)) >= JITA_SEED_MIN_BID
    }
    candidate_ids = local_seed_ids | high_value_jita_ids
    print(f"   snapshot={market_modified}")
    print(
        f"   seed types: 4-H visible={len(local_seed_ids):,}, "
        f"Jita best bid >= {fmt_isk(JITA_SEED_MIN_BID)}={len(high_value_jita_ids):,}, union={len(candidate_ids):,}"
    )
    del market_orders

    print(f"2) Querying EVE Tycoon for 4-H sell orders at structure {STRUCTURE_ID}")
    sell_books, tycoon_checked, tycoon_errors = load_structure_sells_tycoon(candidate_ids)
    print(f"   checked={tycoon_checked:,}, sell types found={len(sell_books):,}, request errors={tycoon_errors:,}")

    print("3) Matching 4-H asks directly into Jita 4-4 buy-order depth")
    rows = []
    profitable_ids = []
    for tid, asks in sell_books.items():
        matched = match_profitable(asks, jita_buys.get(tid, []))
        if not matched:
            continue
        if matched["net_profit"] < MIN_NET_PROFIT or matched["net_roi"] < MIN_NET_ROI:
            continue
        rows.append({"type_id": tid, **matched})
        profitable_ids.append(tid)

    type_objs = fetch_many_ref("types", profitable_ids) if profitable_ids else {}
    for row in rows:
        obj = type_objs.get(int(row["type_id"]))
        row["item_name"] = name_en(obj, str(row["type_id"]))
        row["unit_volume_m3"] = type_volume(obj)
        total_m3 = row["unit_volume_m3"] * row["quantity"]
        row["total_volume_m3"] = total_m3
        row["profit_per_m3"] = row["net_profit"] / total_m3 if total_m3 > 0 else 0.0

    rows.sort(key=lambda r: (r["net_profit"], r["net_roi"], r["profit_per_m3"]), reverse=True)
    rows = rows[:TOP]
    pd.DataFrame(rows).to_csv(RESULT, index=False)

    lines = [
        "# 4-HWWF → Jita 4-4 direct-buy arbitrage",
        "",
        f"- Structure ID: `{STRUCTURE_ID}`",
        f"- Jita EVERef snapshot: `{market_modified}`",
        f"- 4-H sell source: `EVE Tycoon /api/v1/market/orders/{{typeId}}?locationId={STRUCTURE_ID}`",
        f"- Candidate types checked: `{tycoon_checked}`; types with 4-H sells found: `{len(sell_books)}`; request errors: `{tycoon_errors}`",
        f"- Candidate coverage: all type IDs visible at 4-H in regional buy data + all Jita types with best bid >= {fmt_isk(JITA_SEED_MIN_BID)} ISK",
        f"- Sales tax used: `{SALES_TAX_RATE:.4%}`",
        f"- Filters: net profit >= {fmt_isk(MIN_NET_PROFIT)} ISK, ROI >= {MIN_NET_ROI:.1%}",
        "- Revenue assumes immediate liquidation into visible Jita 4-4 buy-order depth; Jita sell orders are never used.",
        "- Net profit is after Jita sales tax but before hauling cost/risk reserve.",
        "",
    ]
    if not rows:
        lines.append("No opportunity passed the current filters in the scanned candidate universe.")
    else:
        lines.extend([
            "| # | Item | Qty | 4-H best sell | Jita best buy | Worst matched bid | Net profit | ROI | Profit/m3 |",
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
    for i, r in enumerate(rows[:30], 1):
        print(
            f"{i:02d}. {r['item_name']} | qty={r['quantity']} | 4-H={fmt_isk(r['four_h_best_sell'])} | "
            f"JitaBuy={fmt_isk(r['jita_best_buy'])} | worstBid={fmt_isk(r['jita_worst_matched_buy'])} | "
            f"net={fmt_isk(r['net_profit'])} | ROI={r['net_roi']:.1%} | profit/m3={fmt_isk(r['profit_per_m3'])}"
        )
    print(f"wrote {RESULT} and {REPORT}")


if __name__ == "__main__":
    main()
