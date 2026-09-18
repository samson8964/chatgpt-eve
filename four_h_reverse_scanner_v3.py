from __future__ import annotations

import os

import pandas as pd

import four_h_contract_scanner as four_h
from contract_deal_scanner import SALES_TAX_RATE
from opportunity_engine_v2 import (
    cross_book_arbitrage,
    drop_best_price_level,
    opportunity_score,
    score_grade,
)
from opportunity_engine_v3 import fetch_live_jita_books
from scanner_source import (
    DATA,
    LATEST,
    MARKET_ORDERS_INDEX,
    download,
    fetch_many_ref,
    latest_file,
    load_market_orders,
    name_en,
    prepare_jita_books,
    type_volume,
)

MIN_PROFIT = float(os.getenv("V3_4H_REVERSE_MIN_PROFIT", "20000000"))
MIN_ROI = float(os.getenv("V3_4H_REVERSE_MIN_ROI", "0.10"))
LIVE_LIMIT = int(os.getenv("V3_4H_REVERSE_LIVE_LIMIT", "160"))
TOP = int(os.getenv("V3_4H_REVERSE_TOP", "100"))
HAUL_BASE = float(os.getenv("V3_4H_REVERSE_HAUL_BASE", "10000000"))
HAUL_PER_M3 = float(os.getenv("V3_4H_REVERSE_HAUL_ISK_PER_M3", "500"))
RESULT = LATEST / "v3_jita_to_four_h.csv"
REPORT = LATEST / "v3_jita_to_four_h.md"


def _net_after_base(q, base):
    if not q:
        return None
    out = dict(q)
    out["haul_cost"] = float(out.get("haul_cost", 0) or 0) + base
    out["net_profit"] = float(out.get("net_profit", 0) or 0) - base
    invested = float(out.get("source_cost", 0) or 0) + float(out.get("haul_cost", 0) or 0)
    out["net_roi"] = out["net_profit"] / invested if invested > 0 else 0.0
    return out


def main():
    LATEST.mkdir(parents=True, exist_ok=True)
    print("Opportunity Engine V3: Jita -> 4-H reverse market arbitrage")

    # Authenticated 4-H order book. build_books gives both sells and buys.
    structure_rows = four_h.fetch_structure_orders()
    _, four_h_buys = four_h.build_books(structure_rows)
    if not four_h_buys:
        pd.DataFrame().to_csv(RESULT, index=False)
        REPORT.write_text("# V3 Jita → 4-H\n\nNo 4-H buy orders.\n", encoding="utf-8")
        return

    # Broad pass against the EVERef snapshot keeps live ESI traffic bounded.
    m_url, m_modified = latest_file(MARKET_ORDERS_INDEX)
    m_path = DATA / m_url.rsplit("/", 1)[-1]
    if not m_path.exists():
        download(m_url, m_path)
    market = load_market_orders(m_path)
    jita_sells, _ = prepare_jita_books(market)
    del market

    broad = []
    for tid, bids in four_h_buys.items():
        asks = jita_sells.get(int(tid), [])
        if not asks:
            continue
        unit_m3 = 0.0
        q = cross_book_arbitrage(
            asks,
            bids,
            SALES_TAX_RATE,
            min_marginal_roi=max(0.0, MIN_ROI * 0.5),
            unit_volume_m3=unit_m3,
            haul_cost_per_m3=0.0,
        )
        q = _net_after_base(q, HAUL_BASE)
        if not q:
            continue
        if q["net_profit"] < MIN_PROFIT * 0.5:
            continue
        broad.append({"type_id": int(tid), "snapshot_profit": q["net_profit"], "snapshot_roi": q["net_roi"]})

    broad.sort(key=lambda r: (r["snapshot_profit"], r["snapshot_roi"]), reverse=True)
    broad = broad[:LIVE_LIMIT]
    ids = {int(r["type_id"]) for r in broad}
    print(f"V3 reverse broad={len(broad)}")

    if not ids:
        pd.DataFrame().to_csv(RESULT, index=False)
        REPORT.write_text("# V3 Jita → 4-H\n\nNo broad candidates.\n", encoding="utf-8")
        return

    types = fetch_many_ref("types", ids)
    live_sells, failed, live_at = fetch_live_jita_books(ids, "sell")

    final = []
    for r in broad:
        tid = int(r["type_id"])
        if tid in failed:
            continue
        unit_m3 = max(0.0, type_volume(types.get(tid)))
        q = cross_book_arbitrage(
            live_sells.get(tid, []),
            four_h_buys.get(tid, []),
            SALES_TAX_RATE,
            min_marginal_roi=max(0.0, MIN_ROI * 0.6),
            unit_volume_m3=unit_m3,
            haul_cost_per_m3=HAUL_PER_M3,
        )
        q = _net_after_base(q, HAUL_BASE)
        if not q or q["net_profit"] < MIN_PROFIT or q["net_roi"] < MIN_ROI:
            continue

        # Stress both sides independently: Jita's cheapest ask disappears or
        # 4-H's best bid disappears. Use the worse result.
        stress_source = _net_after_base(
            cross_book_arbitrage(
                drop_best_price_level(live_sells.get(tid, [])),
                four_h_buys.get(tid, []),
                SALES_TAX_RATE,
                min_marginal_roi=0.0,
                unit_volume_m3=unit_m3,
                haul_cost_per_m3=HAUL_PER_M3,
            ),
            HAUL_BASE,
        )
        stress_dest = _net_after_base(
            cross_book_arbitrage(
                live_sells.get(tid, []),
                drop_best_price_level(four_h_buys.get(tid, [])),
                SALES_TAX_RATE,
                min_marginal_roi=0.0,
                unit_volume_m3=unit_m3,
                haul_cost_per_m3=HAUL_PER_M3,
            ),
            HAUL_BASE,
        )
        stress_values = [
            float(x["net_profit"]) for x in (stress_source, stress_dest) if x is not None
        ]
        stress_profit = min(stress_values) if len(stress_values) == 2 else -float(q["source_cost"])
        status = "SAFE" if stress_profit > 0 else "CHANGED"

        total_m3 = unit_m3 * int(q["quantity"])
        density = q["net_profit"] / total_m3 if total_m3 > 0 else q["net_profit"]
        score = opportunity_score(
            q["net_profit"],
            q["net_roi"],
            density,
            75.0,
            stress_profit,
            1,
            0.5,
            0.0,
            status,
        )
        final.append(
            {
                "engine_version": "Opportunity Engine V3",
                "channel": "JITA_TO_4H",
                "execution_status": status,
                "score_grade": score_grade(score),
                "opportunity_score": score,
                "type_id": tid,
                "item_name": name_en(types.get(tid), str(tid)),
                "quantity": q["quantity"],
                "jita_best_sell": q["source_best"],
                "jita_worst_matched_sell": q["source_worst"],
                "four_h_best_buy": q["destination_best"],
                "four_h_worst_matched_buy": q["destination_worst"],
                "source_cost": q["source_cost"],
                "destination_gross": q["destination_gross"],
                "sales_tax": q["sales_tax"],
                "haul_cost": q["haul_cost"],
                "net_profit": q["net_profit"],
                "net_roi": q["net_roi"],
                "stress_net_profit": stress_profit,
                "unit_volume_m3": unit_m3,
                "total_volume_m3": total_m3,
                "profit_per_m3": density,
                "live_revalidated_at": live_at,
            }
        )

    final.sort(key=lambda x: (x["execution_status"] != "SAFE", -x["opportunity_score"], -x["net_profit"]))
    final = final[:TOP]
    pd.DataFrame(final).to_csv(RESULT, index=False)

    lines = [
        "# Opportunity Engine V3 — Jita → 4-H reverse arbitrage",
        "",
        f"- 4-H orders: `{len(structure_rows)}`",
        f"- Jita snapshot: `{m_modified}`",
        f"- Live revalidation: `{live_at}`",
        f"- Logistics reserve: base `{HAUL_BASE:,.0f}` ISK + `{HAUL_PER_M3:,.0f}` ISK/m³",
        f"- Final opportunities: `{len(final)}`",
        "",
        "Stress test removes the best Jita sell level and the best 4-H buy level separately.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"V3 reverse done: opportunities={len(final)}")


if __name__ == "__main__":
    main()
