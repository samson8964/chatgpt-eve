from __future__ import annotations

import os

import pandas as pd

import structure_market_arbitrage as legacy
from contract_deal_scanner import SALES_TAX_RATE
from opportunity_engine_v2 import (
    analyze_contract_items,
    bundle_liquidity,
    classify_execution_status,
    cross_book_arbitrage,
    drop_best_price_level,
    estimate_transport,
    fetch_jita_history,
    fetch_live_jita_buy_books,
    opportunity_score,
    score_grade,
    snapshot_change_pct,
)
from scanner_source import LATEST, fetch_many_ref, name_en, type_group_id, type_volume

LIVE_LIMIT = int(os.getenv("V31_FOUR_H_MARKET_LIVE_LIMIT", "150"))
HISTORY_LIMIT = int(os.getenv("V31_FOUR_H_MARKET_HISTORY_LIMIT", "80"))
HAUL_BASE = float(os.getenv("V31_FOUR_H_HAUL_BASE", "10000000"))
HAUL_ISK_PER_M3 = float(os.getenv("V31_FOUR_H_HAUL_ISK_PER_M3", "500"))
RESULT = LATEST / "v31_four_h_to_jita_buy.csv"
REPORT = LATEST / "v31_four_h_to_jita_buy.md"


def _with_base_haul(q):
    if not q:
        return None
    out = dict(q)
    out["haul_cost"] = float(out.get("haul_cost", 0.0) or 0.0) + HAUL_BASE
    out["net_profit"] = float(out.get("net_profit", 0.0) or 0.0) - HAUL_BASE
    invested = float(out.get("source_cost", 0.0) or 0.0) + float(out["haul_cost"])
    out["net_roi"] = out["net_profit"] / invested if invested > 0 else 0.0
    return out


def main():
    legacy.main()
    try:
        broad = pd.read_csv(legacy.RESULT)
    except Exception:
        broad = pd.DataFrame()
    if broad.empty or "type_id" not in broad.columns:
        pd.DataFrame().to_csv(RESULT, index=False)
        REPORT.write_text("# V3.1 4-H to Jita\n\nNo broad candidates.\n", encoding="utf-8")
        return

    broad = broad.head(LIVE_LIMIT).copy()
    ids = {int(x) for x in pd.to_numeric(broad["type_id"], errors="coerce").dropna().astype(int)}
    types = fetch_many_ref("types", ids)
    gids = {type_group_id(v) for v in types.values()}
    gids.discard(None)
    groups = fetch_many_ref("groups", gids)

    source_books, source_order_count, source_expires = legacy.load_four_h_sells()
    live_books, failed, live_at = fetch_live_jita_buy_books(ids)

    final = []
    capital_blocked = 0
    for _, r in broad.iterrows():
        tid = int(r["type_id"])
        meta = analyze_contract_items([{"type_id": tid, "quantity": 1}], types, groups)
        if meta.has_highsec_restricted_ship:
            capital_blocked += 1
            continue

        unit_m3 = max(0.0, type_volume(types.get(tid)))
        q = _with_base_haul(
            cross_book_arbitrage(
                source_books.get(tid, []),
                live_books.get(tid, []),
                SALES_TAX_RATE,
                min_marginal_roi=legacy.MIN_NET_ROI,
                unit_volume_m3=unit_m3,
                haul_cost_per_m3=HAUL_ISK_PER_M3,
            )
        )
        if not q or q["net_profit"] < legacy.MIN_NET_PROFIT or q["net_roi"] < legacy.MIN_NET_ROI:
            continue

        stress = _with_base_haul(
            cross_book_arbitrage(
                source_books.get(tid, []),
                drop_best_price_level(live_books.get(tid, [])),
                SALES_TAX_RATE,
                min_marginal_roi=legacy.MIN_NET_ROI,
                unit_volume_m3=unit_m3,
                haul_cost_per_m3=HAUL_ISK_PER_M3,
            )
        )
        stress_profit = stress["net_profit"] if stress else -q["source_cost"]
        snapshot_gross = float(r.get("jita_buy_gross", 0) or 0)
        change = snapshot_change_pct(snapshot_gross, q["destination_gross"])
        status = classify_execution_status(
            True,
            q["net_profit"],
            q["net_roi"],
            stress_profit,
            change,
            ["live_jita_fetch_failed"] if tid in failed else [],
        )
        if status == "DANGER":
            continue

        total_m3 = unit_m3 * q["quantity"]
        final.append(
            {
                "type_id": tid,
                "item_name": name_en(types.get(tid), str(tid)),
                "execution_status": status,
                "quantity": q["quantity"],
                "four_h_best_sell": q["source_best"],
                "four_h_worst_matched_sell": q["source_worst"],
                "jita_best_buy": q["destination_best"],
                "jita_worst_matched_buy": q["destination_worst"],
                "source_cost": q["source_cost"],
                "jita_buy_gross": q["destination_gross"],
                "sales_tax": q["sales_tax"],
                "haul_cost": q["haul_cost"],
                "net_profit": q["net_profit"],
                "net_roi": q["net_roi"],
                "stress_net_profit": stress_profit,
                "snapshot_change_pct": change,
                "live_revalidated_at": live_at,
                "unit_volume_m3": unit_m3,
                "total_volume_m3": total_m3,
                "source_slippage_pct": q["source_slippage_pct"],
                "jita_slippage_pct": q["destination_slippage_pct"],
            }
        )

    final.sort(key=lambda x: (x["net_profit"], x["net_roi"]), reverse=True)
    history_ids = [x["type_id"] for x in final[:HISTORY_LIMIT]]
    history, _ = fetch_jita_history(history_ids)

    for row in final:
        liq = bundle_liquidity({row["type_id"]: row["quantity"]}, history)
        volume = row["total_volume_m3"]
        density = row["net_profit"] / volume if volume > 0 else row["net_profit"]
        transport = estimate_transport(volume, 0, row["net_profit"])
        score = opportunity_score(
            row["net_profit"],
            row["net_roi"],
            density,
            liq["liquidity_score"],
            row["stress_net_profit"],
            1,
            transport.hours,
            row["snapshot_change_pct"],
            row["execution_status"],
        )
        row.update(
            {
                "engine_version": "Opportunity Engine V3.1",
                "score_grade": score_grade(score),
                "opportunity_score": score,
                "profit_per_m3": density,
                "liquidity_score": liq["liquidity_score"],
                "liquidity_label": liq["liquidity_label"],
                "estimated_fill_time_days": liq["fill_time_days"],
                "historical_fill_rate_30d": liq["historical_fill_rate_30d"],
                "transport_trips": transport.trips,
                "estimated_execution_hours": transport.hours,
                "estimated_isk_per_hour": transport.isk_per_hour,
            }
        )

    final.sort(key=lambda x: (x["execution_status"] != "SAFE", -x["opportunity_score"], -x["net_profit"]))
    final = final[:legacy.TOP]
    pd.DataFrame(final).to_csv(RESULT, index=False)

    lines = [
        "# V3.1 4-H to Jita logistics-aware arbitrage",
        "",
        f"- Source orders: {source_order_count}; source cache: {source_expires}",
        f"- Final Jita pricing: live ESI {live_at}",
        f"- Logistics reserve: {HAUL_BASE:,.0f} ISK base + {HAUL_ISK_PER_M3:,.0f} ISK/m3",
        f"- High-sec restricted ships removed: {capital_blocked}",
        f"- Final opportunities: {len(final)}",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"V3.1 4-H market done: opportunities={len(final)} "
        f"capital_blocked={capital_blocked} haul_base={HAUL_BASE:.0f} haul_per_m3={HAUL_ISK_PER_M3:.0f}"
    )


if __name__ == "__main__":
    main()
