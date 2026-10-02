from __future__ import annotations

import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

ESI = "https://esi.evetech.net/latest"
THE_FORGE = 10000002
JITA_44 = 60003760
UA = "chatgpt-eve-compressed-gas-arbitrage/1.0"

DECOMP_EFFICIENCY = float(os.getenv("GAS_DECOMP_EFFICIENCY", "0.90"))
ACCOUNTING_LEVEL = int(os.getenv("ACCOUNTING_LEVEL", "5"))
SALES_TAX_RATE = 0.075 * (1 - 0.11 * ACCOUNTING_LEVEL)
DECOMP_FEE_RESERVE_RATE = float(os.getenv("GAS_DECOMP_FEE_RESERVE_RATE", "0.01"))
WORKERS = int(os.getenv("GAS_SCAN_WORKERS", "8"))

RESULT = Path("results/latest/compressed_gas_decompression_arbitrage.csv")
REPORT = Path("results/latest/compressed_gas_decompression_arbitrage.md")

COMPRESSED_GAS_NAMES = [
    "Compressed Amber Cytoserocin",
    "Compressed Amber Mykoserocin",
    "Compressed Azure Cytoserocin",
    "Compressed Azure Mykoserocin",
    "Compressed Celadon Cytoserocin",
    "Compressed Celadon Mykoserocin",
    "Compressed Chartreuse Cytoserocin",
    "Compressed Fullerite-C28",
    "Compressed Fullerite-C32",
    "Compressed Fullerite-C320",
    "Compressed Fullerite-C50",
    "Compressed Fullerite-C540",
    "Compressed Fullerite-C60",
    "Compressed Fullerite-C70",
    "Compressed Fullerite-C72",
    "Compressed Fullerite-C84",
    "Compressed Gamboge Cytoserocin",
    "Compressed Golden Cytoserocin",
    "Compressed Golden Mykoserocin",
    "Compressed Lime Cytoserocin",
    "Compressed Lime Mykoserocin",
    "Compressed Malachite Cytoserocin",
    "Compressed Malachite Mykoserocin",
    "Compressed Vermillion Cytoserocin",
    "Compressed Vermillion Mykoserocin",
    "Compressed Viridian Cytoserocin",
    "Compressed Viridian Mykoserocin",
]


def req(method: str, url: str, **kwargs):
    last = None
    for attempt in range(4):
        try:
            r = requests.request(method, url, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=60, **kwargs)
            if r.status_code in {420, 429, 500, 502, 503, 504} and attempt < 3:
                time.sleep(1.0 + attempt)
                continue
            r.raise_for_status()
            return r
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(0.7 * (attempt + 1))
    raise RuntimeError(f"{method} {url} failed: {last}")


def resolve_type_ids(names: list[str]) -> dict[str, int]:
    r = req("POST", f"{ESI}/universe/ids/?datasource=tranquility&language=en", json=names)
    data = r.json()
    out = {}
    for row in data.get("inventory_types", []):
        out[str(row["name"])] = int(row["id"])
    return out


def type_info(type_id: int) -> dict:
    return req("GET", f"{ESI}/universe/types/{type_id}/?datasource=tranquility&language=en").json()


def fetch_book(type_id: int, order_type: str) -> list[dict]:
    rows = []
    page = 1
    while True:
        r = req(
            "GET",
            f"{ESI}/markets/{THE_FORGE}/orders/",
            params={
                "datasource": "tranquility",
                "order_type": order_type,
                "type_id": int(type_id),
                "page": page,
            },
        )
        payload = r.json()
        for x in payload or []:
            if int(x.get("location_id") or 0) != JITA_44:
                continue
            if order_type == "sell" and bool(x.get("is_buy_order")):
                continue
            if order_type == "buy" and not bool(x.get("is_buy_order", True)):
                continue
            vol = int(x.get("volume_remain") or 0)
            price = float(x.get("price") or 0)
            if vol <= 0 or price <= 0:
                continue
            rows.append({
                "price": price,
                "vol": vol,
                "min": max(1, int(x.get("min_volume") or 1)),
                "order_id": int(x.get("order_id") or 0),
            })
        pages = max(1, int(r.headers.get("X-Pages", "1") or 1))
        if page >= pages:
            break
        page += 1
    if order_type == "sell":
        rows.sort(key=lambda x: (x["price"], x["order_id"]))
    else:
        rows.sort(key=lambda x: (x["price"], x["order_id"]), reverse=True)
    return rows


def simulate(asks: list[dict], bids: list[dict]) -> dict | None:
    if not asks or not bids:
        return None

    ai = bi = 0
    ask_left = int(asks[0]["vol"])
    bid_left = int(bids[0]["vol"])
    comp_qty = 0
    comp_cost = 0.0
    first_ask = float(asks[0]["price"])
    first_bid = float(bids[0]["price"])
    worst_ask = first_ask
    worst_bid = first_bid
    net_sale_factor = max(0.0, 1.0 - SALES_TAX_RATE - DECOMP_FEE_RESERVE_RATE)

    while ai < len(asks) and bi < len(bids):
        ask = asks[ai]
        bid = bids[bi]
        ap = float(ask["price"])
        bp = float(bid["price"])

        if DECOMP_EFFICIENCY * bp * net_sale_factor <= ap:
            break

        cap_comp = int(math.floor(bid_left / DECOMP_EFFICIENCY + 1e-12))
        if cap_comp <= 0:
            bi += 1
            if bi < len(bids):
                bid_left = int(bids[bi]["vol"])
            continue

        take_comp = min(ask_left, cap_comp)
        ask_min = max(1, int(ask.get("min", 1)))
        if take_comp < ask_min:
            ai += 1
            if ai < len(asks):
                ask_left = int(asks[ai]["vol"])
            continue

        take_normal = min(bid_left, int(math.floor(take_comp * DECOMP_EFFICIENCY + 1e-12)))
        if take_normal <= 0:
            need = int(math.ceil(1.0 / DECOMP_EFFICIENCY))
            if ask_left >= need and bid_left >= 1:
                take_comp = need
                take_normal = 1
            else:
                ai += 1
                if ai < len(asks):
                    ask_left = int(asks[ai]["vol"])
                continue

        comp_qty += take_comp
        comp_cost += ap * take_comp
        worst_ask = ap
        worst_bid = bp
        ask_left -= take_comp
        bid_left -= take_normal

        if ask_left <= 0:
            ai += 1
            if ai < len(asks):
                ask_left = int(asks[ai]["vol"])
        if bid_left <= 0:
            bi += 1
            if bi < len(bids):
                bid_left = int(bids[bi]["vol"])

    if comp_qty <= 0 or comp_cost <= 0:
        return None

    normal_qty = int(math.floor(comp_qty * DECOMP_EFFICIENCY + 1e-12))
    left = normal_qty
    gross = 0.0
    exact_worst_bid = 0.0
    for bid in bids:
        if left <= 0:
            break
        take = min(left, int(bid["vol"]))
        if take < max(1, int(bid.get("min", 1))):
            continue
        gross += take * float(bid["price"])
        exact_worst_bid = float(bid["price"])
        left -= take

    normal_filled = normal_qty - left
    if normal_filled <= 0:
        return None
    if normal_filled < normal_qty:
        comp_needed = int(math.ceil(normal_filled / DECOMP_EFFICIENCY))
        ratio = comp_needed / comp_qty
        comp_qty = comp_needed
        comp_cost *= ratio
        normal_qty = normal_filled

    sales_tax = gross * SALES_TAX_RATE
    decomp_fee_reserve = gross * DECOMP_FEE_RESERVE_RATE
    net_profit = gross - sales_tax - decomp_fee_reserve - comp_cost
    roi = net_profit / comp_cost if comp_cost > 0 else 0.0

    return {
        "compressed_qty": comp_qty,
        "normal_qty_after_90pct": normal_qty,
        "compressed_cost": comp_cost,
        "normal_buy_gross": gross,
        "sales_tax": sales_tax,
        "decompression_fee_reserve": decomp_fee_reserve,
        "net_profit_before_hauling": net_profit,
        "net_roi_before_hauling": roi,
        "compressed_best_sell": first_ask,
        "compressed_worst_sell_used": worst_ask,
        "normal_best_buy": first_bid,
        "normal_worst_buy_used": exact_worst_bid or worst_bid,
    }


def main():
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    normal_names = [x.removeprefix("Compressed ") for x in COMPRESSED_GAS_NAMES]
    ids = resolve_type_ids(COMPRESSED_GAS_NAMES + normal_names)

    pairs = []
    missing = []
    for cname, nname in zip(COMPRESSED_GAS_NAMES, normal_names):
        if cname not in ids or nname not in ids:
            missing.append((cname, nname))
            continue
        pairs.append((cname, ids[cname], nname, ids[nname]))

    all_ids = {tid for _, ctid, _, ntid in pairs for tid in (ctid, ntid)}
    meta = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(type_info, tid): tid for tid in all_ids}
        for fut in as_completed(futs):
            tid = futs[fut]
            try:
                meta[tid] = fut.result()
            except Exception:
                meta[tid] = {}

    def get_pair_books(pair):
        cname, ctid, nname, ntid = pair
        return pair, fetch_book(ctid, "sell"), fetch_book(ntid, "buy")

    rows = []
    failures = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(get_pair_books, p): p for p in pairs}
        for fut in as_completed(futs):
            p = futs[fut]
            try:
                pair, asks, bids = fut.result()
            except Exception as exc:
                failures.append((p[0], str(exc)))
                continue

            cname, ctid, nname, ntid = pair
            m = simulate(asks, bids)
            cobj = meta.get(ctid) or {}
            nobj = meta.get(ntid) or {}
            cvol = float(cobj.get("packaged_volume") or cobj.get("volume") or 0.0)
            nvol = float(nobj.get("packaged_volume") or nobj.get("volume") or 0.0)

            if m:
                outbound_m3 = cvol * m["compressed_qty"]
                return_m3 = nvol * m["normal_qty_after_90pct"]
                total_m3_moved = outbound_m3 + return_m3
                break_even = m["net_profit_before_hauling"] / total_m3_moved if total_m3_moved > 0 else 0.0
                rows.append({
                    "compressed_name": cname,
                    "compressed_type_id": ctid,
                    "normal_name": nname,
                    "normal_type_id": ntid,
                    **m,
                    "compressed_unit_m3": cvol,
                    "normal_unit_m3": nvol,
                    "outbound_compressed_m3": outbound_m3,
                    "return_normal_m3": return_m3,
                    "roundtrip_total_m3": total_m3_moved,
                    "break_even_haul_isk_per_m3": break_even,
                })
            else:
                rows.append({
                    "compressed_name": cname,
                    "compressed_type_id": ctid,
                    "normal_name": nname,
                    "normal_type_id": ntid,
                    "compressed_best_sell": asks[0]["price"] if asks else 0.0,
                    "compressed_worst_sell_used": 0.0,
                    "normal_best_buy": bids[0]["price"] if bids else 0.0,
                    "normal_worst_buy_used": 0.0,
                    "compressed_qty": 0,
                    "normal_qty_after_90pct": 0,
                    "compressed_cost": 0.0,
                    "normal_buy_gross": 0.0,
                    "sales_tax": 0.0,
                    "decompression_fee_reserve": 0.0,
                    "net_profit_before_hauling": 0.0,
                    "net_roi_before_hauling": 0.0,
                    "compressed_unit_m3": cvol,
                    "normal_unit_m3": nvol,
                    "outbound_compressed_m3": 0.0,
                    "return_normal_m3": 0.0,
                    "roundtrip_total_m3": 0.0,
                    "break_even_haul_isk_per_m3": 0.0,
                })

    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values(["net_profit_before_hauling", "net_roi_before_hauling"], ascending=[False, False], inplace=True)
    df.to_csv(RESULT, index=False)

    now = pd.Timestamp.now(tz="UTC").isoformat()
    profitable = df[df["net_profit_before_hauling"] > 0].copy() if not df.empty else pd.DataFrame()
    lines = [
        "# Jita compressed gas -> 90% decompression -> Jita buy orders",
        "",
        f"- Scan time: {now}",
        f"- Decompression efficiency: {DECOMP_EFFICIENCY:.1%}",
        f"- Sales tax: {SALES_TAX_RATE:.3%} (Accounting {ACCOUNTING_LEVEL})",
        f"- Decompression/facility reserve: {DECOMP_FEE_RESERVE_RATE:.2%} of realized gross (conservative proxy)",
        "- Buy side: existing compressed-gas SELL orders in Jita 4-4 (no broker fee).",
        "- Exit side: existing normal-gas BUY orders in Jita 4-4 (no sell-order broker fee).",
        "- Hauling/time cost is not deducted; break-even ISK/m3 is reported for compressed-out + normal-gas-return volume.",
        "",
        f"Profitable gas pairs: **{len(profitable)} / {len(df)}**",
        "",
    ]

    if not profitable.empty:
        lines += [
            "| # | Gas | Comp qty | 90% output | Comp best->worst | Normal buy best->worst | Cost | Gross | Tax | Facility reserve | Net before haul | ROI | Break-even haul ISK/m3 |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for i, r in enumerate(profitable.itertuples(index=False), 1):
            lines.append(
                f"| {i} | {r.normal_name} | {int(r.compressed_qty):,} | {int(r.normal_qty_after_90pct):,} | "
                f"{r.compressed_best_sell:,.2f}->{r.compressed_worst_sell_used:,.2f} | "
                f"{r.normal_best_buy:,.2f}->{r.normal_worst_buy_used:,.2f} | "
                f"{r.compressed_cost/1e6:,.2f}M | {r.normal_buy_gross/1e6:,.2f}M | "
                f"{r.sales_tax/1e6:,.2f}M | {r.decompression_fee_reserve/1e6:,.2f}M | "
                f"**{r.net_profit_before_hauling/1e6:,.2f}M** | {r.net_roi_before_hauling:.1%} | "
                f"{r.break_even_haul_isk_per_m3:,.0f} |"
            )
    else:
        lines.append("No pair is profitable after 90% decompression + tax + facility reserve at current Jita depth.")

    if missing:
        lines += ["", "## Missing type mappings", ""] + [f"- {a} -> {b}" for a, b in missing]
    if failures:
        lines += ["", "## Fetch failures", ""] + [f"- {a}: {b}" for a, b in failures]

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"))
    print("\nCSV_ROWS_BEGIN")
    print(df.to_csv(index=False))
    print("CSV_ROWS_END")


if __name__ == "__main__":
    main()
