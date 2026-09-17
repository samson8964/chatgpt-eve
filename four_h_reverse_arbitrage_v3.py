from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

import structure_market_arbitrage as fourh
from contract_deal_scanner import SALES_TAX_RATE
from opportunity_engine_v2 import cross_book_arbitrage, drop_best_price_level, opportunity_score, score_grade
from opportunity_engine_v3 import fetch_live_jita_sell_books
from scanner_source import DATA, JITA_SYSTEM, LATEST, MARKET_ORDERS_INDEX, download, fetch_many_ref, latest_file, load_market_orders, name_en, prepare_jita_books, route_jumps, type_volume

ENGINE = "Opportunity Engine V3"
FOUR_H_SYSTEM_ID = int(os.getenv("FOUR_H_SYSTEM_ID", "30000240"))
MIN_NET_PROFIT = float(os.getenv("FOUR_H_V3_REVERSE_MIN_NET_PROFIT", "20000000"))
MIN_NET_ROI = float(os.getenv("FOUR_H_V3_REVERSE_MIN_NET_ROI", "0.10"))
TOP = int(os.getenv("FOUR_H_V3_REVERSE_TOP", "100"))
LIVE_LIMIT = int(os.getenv("FOUR_H_V3_REVERSE_LIVE_LIMIT", "150"))
HAUL_BASE_ISK = float(os.getenv("FOUR_H_V3_HAUL_BASE_ISK", "5000000"))
HAUL_ISK_PER_M3_JUMP = float(os.getenv("FOUR_H_V3_HAUL_ISK_PER_M3_JUMP", "1000"))
RESULT = LATEST / "four_h_reverse_v3.csv"
REPORT = LATEST / "four_h_reverse_v3.md"


def _load_four_h_buys():
    first = fourh.fetch_structure_page(1)
    pages = max(1, int(first.get("pages") or 1))
    raw = list(first.get("orders") or [])
    for page in range(2, pages + 1):
        raw.extend(fourh.fetch_structure_page(page).get("orders") or [])
    books = {}
    for row in raw:
        if not bool(row.get("is_buy_order")):
            continue
        try:
            tid = int(row["type_id"])
            price = float(row["price"])
            vol = int(row.get("volume_remain") or 0)
            minv = max(1, int(row.get("min_volume") or 1))
        except Exception:
            continue
        if tid <= 0 or price <= 0 or vol <= 0:
            continue
        books.setdefault(tid, []).append({"price": price, "vol": vol, "min": minv, "order_id": int(row.get("order_id") or 0)})
    for book in books.values():
        book.sort(key=lambda x: (x["price"], x["order_id"]), reverse=True)
    return books, len(raw), first.get("expires")


def _after_fixed_haul(q, fixed):
    if not q:
        return None
    out = dict(q)
    out["haul_cost"] = float(q.get("haul_cost", 0) or 0) + fixed
    out["net_profit"] = float(q.get("net_profit", 0) or 0) - fixed
    invested = float(q.get("source_cost", 0) or 0) + out["haul_cost"]
    out["net_roi"] = out["net_profit"] / invested if invested > 0 else 0.0
    return out


def main():
    LATEST.mkdir(parents=True, exist_ok=True)
    print("V3 4-H reverse 1) authenticated 4-H buy book + Jita snapshot")
    four_h_buys, order_count, expires = _load_four_h_buys()
    m_url, m_modified = latest_file(MARKET_ORDERS_INDEX)
    m_path = DATA / Path(m_url).name
    if not m_path.exists():
        download(m_url, m_path)
    orders = load_market_orders(m_path)
    jita_sells, _ = prepare_jita_books(orders)
    del orders

    jumps = route_jumps(JITA_SYSTEM, FOUR_H_SYSTEM_ID, "shortest")
    if jumps < 0:
        raise RuntimeError("Cannot resolve Jita -> 4-HWWF route; reverse arbitrage stopped conservatively")
    variable_per_m3 = jumps * HAUL_ISK_PER_M3_JUMP

    candidate_ids = sorted(set(four_h_buys).intersection(jita_sells))
    type_objs = fetch_many_ref("types", candidate_ids) if candidate_ids else {}
    broad = []
    for tid in candidate_ids:
        unit_m3 = max(0.0, type_volume(type_objs.get(tid)))
        q = cross_book_arbitrage(jita_sells.get(tid, []), four_h_buys.get(tid, []), SALES_TAX_RATE, min_marginal_roi=MIN_NET_ROI * 0.5, unit_volume_m3=unit_m3, haul_cost_per_m3=variable_per_m3)
        q = _after_fixed_haul(q, HAUL_BASE_ISK)
        if not q or q["net_profit"] < MIN_NET_PROFIT * 0.25:
            continue
        broad.append({"type_id": tid, "snapshot_profit": q["net_profit"], "snapshot_roi": q["net_roi"], "unit_m3": unit_m3})
    broad.sort(key=lambda r: (r["snapshot_profit"], r["snapshot_roi"]), reverse=True)
    broad = broad[:LIVE_LIMIT]
    ids = [r["type_id"] for r in broad]
    print(f"V3 4-H reverse broad={len(broad)} route_jumps={jumps} variable_haul={variable_per_m3:.0f} ISK/m3")
    live_sells, failed, live_at = fetch_live_jita_sell_books(ids)

    rows = []
    for r in broad:
        tid = int(r["type_id"])
        if tid in failed:
            continue
        unit_m3 = r["unit_m3"]
        q = cross_book_arbitrage(live_sells.get(tid, []), four_h_buys.get(tid, []), SALES_TAX_RATE, min_marginal_roi=MIN_NET_ROI, unit_volume_m3=unit_m3, haul_cost_per_m3=variable_per_m3)
        q = _after_fixed_haul(q, HAUL_BASE_ISK)
        if not q or q["net_profit"] < MIN_NET_PROFIT or q["net_roi"] < MIN_NET_ROI:
            continue
        stress = cross_book_arbitrage(drop_best_price_level(live_sells.get(tid, [])), drop_best_price_level(four_h_buys.get(tid, [])), SALES_TAX_RATE, min_marginal_roi=MIN_NET_ROI, unit_volume_m3=unit_m3, haul_cost_per_m3=variable_per_m3)
        stress = _after_fixed_haul(stress, HAUL_BASE_ISK)
        stress_profit = stress["net_profit"] if stress else -float(q["source_cost"])
        status = "SAFE" if stress_profit > 0 else "CHANGED"
        volume = unit_m3 * q["quantity"]
        density = q["net_profit"] / volume if volume > 0 else q["net_profit"]
        execution_hours = max(0.25, (jumps * 2 * 50) / 3600 + 0.2)
        score = opportunity_score(q["net_profit"], q["net_roi"], density, 100.0, stress_profit, 2, execution_hours, 0.0, status)
        rows.append({
            "engine_version": ENGINE,
            "opportunity_class": "JITA_TO_4H",
            "execution_status": status,
            "score_grade": score_grade(score),
            "opportunity_score": score,
            "type_id": tid,
            "item_name": name_en(type_objs.get(tid), str(tid)),
            "quantity": q["quantity"],
            "jita_best_sell": q["source_best"],
            "jita_worst_matched_sell": q["source_worst"],
            "four_h_best_buy": q["destination_best"],
            "four_h_worst_matched_buy": q["destination_worst"],
            "source_cost": q["source_cost"],
            "destination_gross": q["destination_gross"],
            "sales_tax": q["sales_tax"],
            "haul_cost": q["haul_cost"],
            "route_jumps": jumps,
            "haul_isk_per_m3_jump": HAUL_ISK_PER_M3_JUMP,
            "net_profit": q["net_profit"],
            "net_roi": q["net_roi"],
            "stress_net_profit": stress_profit,
            "unit_volume_m3": unit_m3,
            "total_volume_m3": volume,
            "profit_per_m3": density,
            "verified_at": live_at,
        })

    rows.sort(key=lambda x: (x["execution_status"] != "SAFE", -x["opportunity_score"], -x["net_profit"]))
    rows = rows[:TOP]
    pd.DataFrame(rows).to_csv(RESULT, index=False)
    lines = ["# Opportunity Engine V3 — Jita -> 4-H reverse arbitrage", "", f"- 4-H orders: `{order_count}`; cache: `{expires}`", f"- Jita snapshot: `{m_modified}`; live asks: `{live_at}`", f"- Route: Jita -> 4-HWWF `{jumps}` shortest jumps", f"- Haul reserve: base `{HAUL_BASE_ISK:,.0f}` + `{HAUL_ISK_PER_M3_JUMP:,.0f}` ISK/m3/jump", "- SAFE requires the opportunity to remain profitable after removing the best Jita ask level and best 4-H bid level.", ""]
    if rows:
        lines += ["| # | Grade | Status | Item | Qty | Jita ask | 4-H bid | Net | ROI | Stress |", "|---:|---|---|---|---:|---:|---:|---:|---:|---:|"]
        for i, x in enumerate(rows, 1):
            lines.append(f"| {i} | {x['score_grade']} | {x['execution_status']} | {x['item_name']} | {x['quantity']:,} | {x['jita_best_sell']/1e6:.2f}M | {x['four_h_best_buy']/1e6:.2f}M | {x['net_profit']/1e6:.1f}M | {x['net_roi']:.1%} | {x['stress_net_profit']/1e6:.1f}M |")
    else:
        lines.append("No reverse opportunity passed V3 live/stress filters.")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"V3 4-H reverse done: opportunities={len(rows)}")


if __name__ == "__main__":
    main()
