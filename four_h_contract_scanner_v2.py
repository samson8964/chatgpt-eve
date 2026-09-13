from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd

import four_h_contract_scanner as legacy
from contract_deal_scanner import SALES_TAX_RATE
from opportunity_engine_v2 import (
    analyze_contract_items,
    classify_execution_status,
    drop_best_price_level,
    fetch_live_jita_buy_books,
    liquidate_bundle,
    opportunity_score,
    score_grade,
)
from scanner_source import (
    DATA,
    PUBLIC_CONTRACTS_INDEX,
    download,
    fetch_many_ref,
    latest_file,
    load_contracts,
    name_en,
    truthy_series,
    type_group_id,
    type_volume,
)


def _aggregate(df):
    out = defaultdict(int)
    for r in df.itertuples(index=False):
        try:
            tid, qty = int(r.type_id), int(r.quantity)
        except Exception:
            continue
        if tid > 0 and qty > 0:
            out[tid] += qty
    return dict(out)


def main():
    # V1 remains the broad detector. V2 replaces the final valuation and ranking.
    legacy.main()
    try:
        broad = pd.read_csv(legacy.RESULT)
    except Exception:
        broad = pd.DataFrame()
    if broad.empty or "contract_id" not in broad.columns:
        return

    ids = {int(x) for x in pd.to_numeric(broad["contract_id"], errors="coerce").dropna().astype(int)}
    c_url, c_modified = latest_file(PUBLIC_CONTRACTS_INDEX)
    c_path = DATA / Path(c_url).name
    if not c_path.exists():
        download(c_url, c_path)
    _, items = load_contracts(c_path)
    ii = items[items["contract_id"].isin(ids)].copy()
    ii["_included"] = truthy_series(ii["is_included"])
    ii["_bpc"] = truthy_series(ii["is_blueprint_copy"])
    ii["quantity"] = pd.to_numeric(ii["quantity"], errors="coerce").fillna(0).astype(int)
    ii["type_id"] = pd.to_numeric(ii["type_id"], errors="coerce").fillna(0).astype(int)
    ii = ii[ii["_included"] & ~ii["_bpc"] & (ii["quantity"] > 0) & (ii["type_id"] > 0)]
    raw = {int(cid): g.to_dict("records") for cid, g in ii.groupby("contract_id", sort=False)}
    type_ids = {int(x) for x in ii["type_id"].dropna().astype(int)}
    types = fetch_many_ref("types", type_ids)
    gids = {type_group_id(v) for v in types.values()}
    gids.discard(None)
    groups = fetch_many_ref("groups", gids)

    source_rows = legacy.fetch_structure_orders()
    _, local_buys = legacy.build_books(source_rows)

    feasibility = {}
    wanted = set()
    for cid in ids:
        f = analyze_contract_items(raw.get(cid, []), types, groups)
        if f.adjusted_itemq:
            feasibility[cid] = f
            wanted.update(f.adjusted_itemq)
    live_jita, failed, live_at = fetch_live_jita_buy_books(wanted)

    rows = []
    for _, r in broad.iterrows():
        cid = int(r["contract_id"])
        f = feasibility.get(cid)
        if not f:
            continue
        itemq = f.adjusted_itemq
        price = float(r.get("price", 0) or 0)
        total_m3 = sum(max(0.0, type_volume(types.get(tid))) * qty for tid, qty in itemq.items())

        local = liquidate_bundle(itemq, local_buys, SALES_TAX_RATE)
        local_profit = float(local["net_after_tax"] or 0) - price if local["complete"] else float("-inf")
        local_roi = local_profit / price if price > 0 and local["complete"] else float("-inf")
        local_stress_books = {tid: drop_best_price_level(local_buys.get(tid, [])) for tid in itemq}
        local_stress = liquidate_bundle(itemq, local_stress_books, SALES_TAX_RATE)
        local_stress_profit = float(local_stress["net_after_tax"] or 0) - price

        jita = None
        jita_profit = jita_roi = jita_stress_profit = float("-inf")
        if not f.has_highsec_restricted_ship and not set(itemq).intersection(failed):
            jita = liquidate_bundle(itemq, live_jita, SALES_TAX_RATE)
            if jita["complete"]:
                jita_profit = float(jita["net_after_tax"] or 0) - price
                jita_roi = jita_profit / price if price > 0 else 0.0
            stress_books = {tid: drop_best_price_level(live_jita.get(tid, [])) for tid in itemq}
            jita_stress = liquidate_bundle(itemq, stress_books, SALES_TAX_RATE)
            jita_stress_profit = float(jita_stress["net_after_tax"] or 0) - price

        if local_profit >= jita_profit:
            route, quote = "4-H local buy", local
            profit, roi, stress_profit = local_profit, local_roi, local_stress_profit
        else:
            route, quote = "Jita 4-4 live buy", jita
            profit, roi, stress_profit = jita_profit, jita_roi, jita_stress_profit

        if quote is None or not quote["complete"] or profit < legacy.MIN_NET_PROFIT or roi < legacy.MIN_NET_ROI:
            continue
        status = classify_execution_status(True, profit, roi, stress_profit, 0.0, [])
        if status == "DANGER":
            continue
        density = profit / total_m3 if total_m3 > 0 else profit
        # Immediate buy-book liquidation is already executable; use a neutral/high liquidity
        # score here and let the stress test penalize fragile books.
        liq_score = 100.0 if route.startswith("4-H") else 80.0
        score = opportunity_score(profit, roi, density, liq_score, stress_profit, 0, 0.2, 0.0, status)
        details = sorted(quote["rows"], key=lambda x: float(x.get("gross", 0) or 0), reverse=True)
        top = [
            f"{name_en(types.get(int(x['type_id'])), str(x['type_id']))} x{int(x['quantity'])} @ {legacy.fmt_isk(x['vwap'])}"
            for x in details[:5]
        ]
        rows.append({
            "engine_version": "Opportunity Engine V2",
            "contract_id": cid,
            "title": str(r.get("title", "")),
            "price": price,
            "best_route": route,
            "execution_status": status,
            "score_grade": score_grade(score),
            "opportunity_score": score,
            "best_net_profit": profit,
            "best_roi": roi,
            "stress_net_profit": stress_profit,
            "packaged_volume_m3": total_m3,
            "profit_per_m3": density,
            "excluded_rig_types": len(f.excluded_rigs),
            "excluded_rig_qty": sum(f.excluded_rigs.values()),
            "highsec_restricted_ship": f.has_highsec_restricted_ship,
            "live_revalidated_at": live_at,
            "top_items": "; ".join(top),
        })

    rows.sort(key=lambda x: (x["execution_status"] != "SAFE", -x["opportunity_score"], -x["best_net_profit"]))
    rows = rows[:legacy.TOP]
    pd.DataFrame(rows).to_csv(legacy.RESULT, index=False)

    lines = [
        "# 4-HWWF contract bargain scan — Opportunity Engine V2",
        "",
        f"- Public contract snapshot: `{c_modified}`",
        f"- Current 4-H structure orders: `{len(source_rows)}`",
        f"- Jita final pricing: live ESI `{live_at}`",
        "- Likely fitted rigs are excluded from recoverable value.",
        "- High-sec restricted ships may use 4-H local liquidation, but never the Jita route.",
        "",
    ]
    if rows:
        lines += [
            "| # | Grade | Status | Contract | Title | Price | Route | Net | ROI | Score | m3 | Rigs excluded |",
            "|---:|---|---|---:|---|---:|---|---:|---:|---:|---:|---:|",
        ]
        for i, x in enumerate(rows, 1):
            lines.append(
                f"| {i} | {x['score_grade']} | {x['execution_status']} | {x['contract_id']} | {x['title'].replace('|','/')} | "
                f"{legacy.fmt_isk(x['price'])} | {x['best_route']} | {legacy.fmt_isk(x['best_net_profit'])} | "
                f"{x['best_roi']:.1%} | {x['opportunity_score']:.1f} | {x['packaged_volume_m3']:.0f} | {x['excluded_rig_qty']} |"
            )
    else:
        lines.append("No V2 opportunity passed live execution checks.")
    legacy.REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"V2 4-H contracts done: bargains={len(rows)}")


if __name__ == "__main__":
    main()
