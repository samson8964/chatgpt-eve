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
from scanner_source import fetch_many_ref, name_en, type_group_id, type_volume

LIVE_LIMIT = int(os.getenv("V2_FOUR_H_MARKET_LIVE_LIMIT", "150"))
HISTORY_LIMIT = int(os.getenv("V2_FOUR_H_MARKET_HISTORY_LIMIT", "80"))
HAUL_ISK_PER_M3 = float(os.getenv("FOUR_H_HAUL_ISK_PER_M3", "0"))


def main():
    # Reuse the proven V1 broad pass: authenticated 4-H source orders + EVERef Jita snapshot.
    legacy.main()
    try:
        broad = pd.read_csv(legacy.RESULT)
    except Exception:
        broad = pd.DataFrame()
    if broad.empty or "type_id" not in broad.columns:
        return

    broad = broad.head(LIVE_LIMIT).copy()
    ids = {int(x) for x in pd.to_numeric(broad["type_id"], errors="coerce").dropna().astype(int)}
    types = fetch_many_ref("types", ids)
    gids = {type_group_id(v) for v in types.values()}
    gids.discard(None)
    groups = fetch_many_ref("groups", gids)

    # Pull the source book again so both sides are current during final validation.
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
        q = cross_book_arbitrage(
            source_books.get(tid, []),
            live_books.get(tid, []),
            SALES_TAX_RATE,
            min_marginal_roi=legacy.MIN_NET_ROI,
            unit_volume_m3=unit_m3,
            haul_cost_per_m3=HAUL_ISK_PER_M3,
        )
        if not q or q["net_profit"] < legacy.MIN_NET_PROFIT or q["net_roi"] < legacy.MIN_NET_ROI:
            continue
        stress = cross_book_arbitrage(
            source_books.get(tid, []),
            drop_best_price_level(live_books.get(tid, [])),
            SALES_TAX_RATE,
            min_marginal_roi=legacy.MIN_NET_ROI,
            unit_volume_m3=unit_m3,
            haul_cost_per_m3=HAUL_ISK_PER_M3,
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
        final.append({
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
            "total_volume_m3": unit_m3 * q["quantity"],
            "source_slippage_pct": q["source_slippage_pct"],
            "jita_slippage_pct": q["destination_slippage_pct"],
        })

    final.sort(key=lambda x: (x["net_profit"], x["net_roi"]), reverse=True)
    history_ids = [x["type_id"] for x in final[:HISTORY_LIMIT]]
    history, _ = fetch_jita_history(history_ids)

    for row in final:
        liq = bundle_liquidity({row["type_id"]: row["quantity"]}, history)
        volume = row["total_volume_m3"]
        density = row["net_profit"] / volume if volume > 0 else row["net_profit"]
        transport = estimate_transport(volume, 0, row["net_profit"])
        score = opportunity_score(
            row["net_profit"], row["net_roi"], density, liq["liquidity_score"],
            row["stress_net_profit"], 1, transport.hours, row["snapshot_change_pct"], row["execution_status"],
        )
        row.update({
            "engine_version": "Opportunity Engine V2",
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
        })

    final.sort(key=lambda x: (x["execution_status"] != "SAFE", -x["opportunity_score"], -x["net_profit"]))
    final = final[:legacy.TOP]
    pd.DataFrame(final).to_csv(legacy.RESULT, index=False)

    lines = [
        "# 4-HWWF → Jita 4-4 Opportunity Engine V2",
        "",
        f"- Source orders: `{source_order_count}`; source cache: `{source_expires}`",
        f"- Final Jita pricing: live ESI `{live_at}`",
        f"- High-sec restricted ships removed: `{capital_blocked}`",
        "- Final ranking uses live depth, stress survival, liquidity and volume density.",
        "",
    ]
    if final:
        lines += [
            "| # | Grade | Status | Item | Qty | 4-H | Jita live buy | Net | ROI | Score | ISK/m3 | Liquidity |",
            "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
        for i, r in enumerate(final, 1):
            lines.append(
                f"| {i} | {r['score_grade']} | {r['execution_status']} | {r['item_name']} | {r['quantity']:,} | "
                f"{legacy.fmt_isk(r['four_h_best_sell'])} | {legacy.fmt_isk(r['jita_best_buy'])} | "
                f"{legacy.fmt_isk(r['net_profit'])} | {r['net_roi']:.1%} | {r['opportunity_score']:.1f} | "
                f"{legacy.fmt_isk(r['profit_per_m3'])} | {r['liquidity_label']} |"
            )
    else:
        lines.append("No live-revalidated opportunity passed the V2 filters.")
    legacy.REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"V2 4-H market done: opportunities={len(final)} capital_blocked={capital_blocked}")


if __name__ == "__main__":
    main()
