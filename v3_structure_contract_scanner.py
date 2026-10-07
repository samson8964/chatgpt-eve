from __future__ import annotations

import math
import os
from pathlib import Path

import pandas as pd

from contract_deal_scanner import SALES_TAX_RATE
from opportunity_engine_v2 import (
    drop_best_price_level,
    opportunity_score,
    profit_density,
    score_grade,
)
from opportunity_engine_v3 import fetch_live_jita_books, partial_liquidation
from scanner_source import (
    DATA,
    LATEST,
    MARKET_ORDERS_INDEX,
    PUBLIC_CONTRACTS_INDEX,
    download,
    fetch_many_ref,
    latest_file,
    load_contracts,
    load_market_orders,
    name_en,
    prepare_jita_books,
    truthy_series,
    type_volume,
)
from v3_engine import ExecutionProof, PolicyConfig, RejectionFunnel, evaluate_execution, is_full_cash_exit

SOURCE_KEY = (os.getenv("V3_STRUCTURE_KEY", "structure") or "structure").strip().lower().replace(" ", "_")
SOURCE_LABEL = (os.getenv("SOURCE_LABEL", SOURCE_KEY) or SOURCE_KEY).strip()
STRUCTURE_ID = int(os.getenv("SOURCE_STRUCTURE_ID", os.getenv("FOUR_H_STRUCTURE_ID", "0")) or 0)
MIN_PRICE = float(os.getenv("SOURCE_CONTRACT_MIN_PRICE", "1000000"))
MAX_PRICE = float(os.getenv("SOURCE_CONTRACT_MAX_PRICE", "5000000000"))
MIN_HOURS_TO_EXPIRE = float(os.getenv("SOURCE_CONTRACT_MIN_HOURS_TO_EXPIRE", "0.25"))
LIVE_LIMIT = int(os.getenv("V3_STRUCTURE_CONTRACT_LIVE_LIMIT", "160"))
TOP = int(os.getenv("V3_STRUCTURE_CONTRACT_TOP", "120"))
HAUL_BASE = float(os.getenv("V3_STRUCTURE_HAUL_BASE", "10000000"))
HAUL_PER_M3 = float(os.getenv("V3_STRUCTURE_HAUL_ISK_PER_M3", "500"))

RESULT = LATEST / os.getenv("V3_STRUCTURE_CONTRACT_RESULT_CSV", f"v3_{SOURCE_KEY}_contracts.csv")
REPORT = LATEST / os.getenv("V3_STRUCTURE_CONTRACT_REPORT_MD", f"v3_{SOURCE_KEY}_contracts.md")
FUNNEL_PATH = LATEST / os.getenv("V3_STRUCTURE_CONTRACT_FUNNEL_JSON", f"v3_{SOURCE_KEY}_contracts_funnel.json")


def aggregate_items(df: pd.DataFrame) -> dict[int, int]:
    out: dict[int, int] = {}
    for r in df.itertuples(index=False):
        try:
            tid = int(r.type_id)
            qty = int(r.quantity)
        except Exception:
            continue
        if tid > 0 and qty > 0:
            out[tid] = out.get(tid, 0) + qty
    return out


def total_volume(itemq: dict[int, int], types: dict[int, dict]) -> float:
    return sum(max(0.0, float(type_volume(types.get(int(tid))) or 0.0)) * int(qty) for tid, qty in itemq.items())


def structure_haul(total_m3: float) -> float:
    return max(0.0, HAUL_BASE) + max(0.0, total_m3) * max(0.0, HAUL_PER_M3)


def choose_candidate_ids(rows: list[dict], limit: int) -> list[int]:
    if not rows or limit <= 0:
        return []
    by_profit = sorted(rows, key=lambda r: float(r.get("snapshot_profit", -math.inf)), reverse=True)
    by_roi = sorted(rows, key=lambda r: float(r.get("snapshot_roi", -math.inf)), reverse=True)
    by_new = sorted(rows, key=lambda r: str(r.get("date_issued", "")), reverse=True)
    chosen: dict[int, None] = {}
    for bucket, quota in ((by_profit, int(limit * 0.55)), (by_roi, int(limit * 0.25)), (by_new, int(limit * 0.20))):
        for row in bucket[: max(1, quota)]:
            chosen[int(row["contract_id"])] = None
    for row in by_profit:
        if len(chosen) >= limit:
            break
        chosen.setdefault(int(row["contract_id"]), None)
    return list(chosen)[:limit]


def _format_items(itemq: dict[int, int], types: dict[int, dict], limit: int = 12) -> str:
    return " | ".join(
        f"{name_en(types.get(int(tid)), str(tid))} x{int(qty)}"
        for tid, qty in list(itemq.items())[:limit]
    )


def main() -> None:
    if STRUCTURE_ID <= 0:
        raise RuntimeError("SOURCE_STRUCTURE_ID/FOUR_H_STRUCTURE_ID is required")

    from four_h_contract_scanner import build_books, fetch_structure_orders

    LATEST.mkdir(parents=True, exist_ok=True)
    funnel = RejectionFunnel()
    cfg = PolicyConfig.from_env()
    print(f"V3 structure contracts: {SOURCE_LABEL} ({STRUCTURE_ID})")

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
        & (contracts["price"] <= MAX_PRICE)
    ].copy()
    if "date_expired" in c.columns:
        exp = pd.to_datetime(c["date_expired"], utc=True, errors="coerce")
        c = c[exp.isna() | (exp > pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=MIN_HOURS_TO_EXPIRE))].copy()
    funnel.stage("active_contracts", len(c))

    valid_ids = set(c["contract_id"].dropna().astype(int))
    ii = items[items["contract_id"].isin(valid_ids)].copy()
    ii["contract_id"] = pd.to_numeric(ii["contract_id"], errors="coerce").astype("Int64")
    ii["_included"] = truthy_series(ii["is_included"])
    ii["_bpc"] = truthy_series(ii["is_blueprint_copy"])
    ii["quantity"] = pd.to_numeric(ii["quantity"], errors="coerce").fillna(0).astype(int)
    ii["type_id"] = pd.to_numeric(ii["type_id"], errors="coerce").fillna(0).astype(int)

    requested_ids = set(ii.loc[~ii["_included"], "contract_id"].dropna().astype(int))
    bpc_ids = set(ii.loc[ii["_bpc"], "contract_id"].dropna().astype(int))
    if requested_ids:
        funnel.reject("REQUESTED_ITEMS_DEFER_TO_PUBLIC_BARTER", len(requested_ids))
    if bpc_ids:
        funnel.reject("BPC_DEFER_TO_BPC_ENGINE", len(bpc_ids))
    usable_ids = valid_ids - requested_ids - bpc_ids
    c = c[c["contract_id"].isin(usable_ids)].copy()
    inc = ii[ii["contract_id"].isin(usable_ids) & ii["_included"] & (ii["quantity"] > 0) & (ii["type_id"] > 0)].copy()
    grouped = {int(cid): aggregate_items(g) for cid, g in inc.groupby("contract_id", sort=False)}
    funnel.stage("plain_item_contracts", len(grouped))

    structure_rows = fetch_structure_orders()
    _, local_buys = build_books(structure_rows)

    market = load_market_orders(m_path)
    _, snapshot_jita_buys = prepare_jita_books(market)
    del market

    c_by_id = c.set_index("contract_id", drop=False)
    prelim: list[dict] = []
    for cid, itemq in grouped.items():
        if cid not in c_by_id.index or not itemq:
            continue
        cr = c_by_id.loc[cid]
        if isinstance(cr, pd.DataFrame):
            cr = cr.iloc[0]
        price = float(cr.get("price") or 0.0)
        local = partial_liquidation(itemq, local_buys, SALES_TAX_RATE)
        jita = partial_liquidation(itemq, snapshot_jita_buys, SALES_TAX_RATE)
        local_profit = float(local["net_after_tax"]) - price
        jita_profit = float(jita["net_after_tax"]) - price
        best_profit = max(local_profit, jita_profit)
        best_roi = best_profit / price if price > 0 else -math.inf
        prelim.append(
            {
                "contract_id": cid,
                "price": price,
                "itemq": itemq,
                "snapshot_profit": best_profit,
                "snapshot_roi": best_roi,
                "date_issued": cr.get("date_issued", ""),
                "date_expired": cr.get("date_expired", ""),
                "title": cr.get("title", ""),
            }
        )
    funnel.stage("prefilter_candidates", len(prelim))

    candidate_ids = choose_candidate_ids(prelim, LIVE_LIMIT)
    candidate_set = set(candidate_ids)
    selected = {int(r["contract_id"]): r for r in prelim if int(r["contract_id"]) in candidate_set}
    funnel.stage("deep_validation_contracts", len(selected))
    if not selected:
        pd.DataFrame().to_csv(RESULT, index=False)
        funnel.write_json(FUNNEL_PATH)
        REPORT.write_text(f"# V3 {SOURCE_LABEL} contracts\n\nNo candidates.\n", "utf-8")
        return

    tids = sorted({int(tid) for p in selected.values() for tid in p["itemq"]})
    types = fetch_many_ref("types", tids)
    live_jita_buys, failed_jita, live_at = fetch_live_jita_books(tids, "buy")

    rows: list[dict] = []
    for cid, p in selected.items():
        itemq = p["itemq"]
        jita_failed_here = bool(set(itemq).intersection(failed_jita))
        if jita_failed_here:
            funnel.reject("JITA_LIVE_BOOK_FAILED")

        local = partial_liquidation(itemq, local_buys, SALES_TAX_RATE)
        jita = partial_liquidation(itemq, live_jita_buys, SALES_TAX_RATE)
        volume_m3 = total_volume(itemq, types)
        jita_haul = structure_haul(volume_m3)
        local_profit = float(local["net_after_tax"]) - float(p["price"])
        jita_profit = float(jita["net_after_tax"]) - float(p["price"]) - jita_haul

        if local_profit >= jita_profit:
            exit_market = f"{SOURCE_LABEL} local buy"
            quote = local
            exit_books = local_buys
            haul = 0.0
        else:
            exit_market = "Jita 4-4 buy"
            quote = jita
            exit_books = live_jita_buys
            haul = jita_haul

        requested_units = int(quote["requested_units"])
        filled_units = int(quote["filled_units"])
        full = is_full_cash_exit(
            coverage=float(quote["coverage"]),
            filled_units=filled_units,
            requested_units=requested_units,
        )
        route = "FULL_CASH" if full else "PARTIAL_CASH_FLOOR"

        stressed_books = {
            int(tid): drop_best_price_level(exit_books.get(int(tid), []))
            for tid in itemq
        }
        stress = partial_liquidation(itemq, stressed_books, SALES_TAX_RATE)
        stress_profit = float(stress["net_after_tax"]) - float(p["price"]) - haul
        net_profit = float(quote["net_after_tax"]) - float(p["price"]) - haul
        invested = float(p["price"]) + haul
        net_roi = net_profit / invested if invested > 0 else 0.0
        density = profit_density(net_profit, volume_m3)

        proof = ExecutionProof(
            opportunity_id=f"{SOURCE_KEY}:contract:{cid}",
            channel=route,
            source_cost=float(p["price"]),
            destination_value=float(quote["gross"]),
            sales_tax=float(quote["sales_tax"]),
            haul_cost=haul,
            volume_m3=volume_m3,
            source_depth_complete=True,
            destination_depth_complete=full,
            access_verified=True,
            stress_value=float(stress["gross"]),
            live_timestamp=str(live_at),
            coverage=float(quote["coverage"]),
            net_profit=net_profit,
            net_roi=net_roi,
            stress_net_profit=stress_profit,
            profit_per_m3=density,
            market_change_pct=0.0,
            fatal=filled_units <= 0 or (exit_market == "Jita 4-4 buy" and jita_failed_here),
            details={
                "contract_id": cid,
                "contract_price": float(p["price"]),
                "source_key": SOURCE_KEY,
                "source_label": SOURCE_LABEL,
                "structure_id": STRUCTURE_ID,
                "exit_market": exit_market,
                "cash_floor_gross": float(quote["gross"]),
                "cash_floor_coverage": float(quote["coverage"]),
                "cash_floor_filled_units": filled_units,
                "bundle_total_units": requested_units,
                "leftover_units_valued_zero": max(0, requested_units - filled_units),
                "items": _format_items(itemq, types),
                "contract_title": str(p.get("title") or ""),
                "date_issued": p.get("date_issued", ""),
                "date_expired": p.get("date_expired", ""),
            },
        )
        decision = evaluate_execution(proof, cfg)
        if decision.stage in {"RESEARCH", "WATCH", "DANGER"}:
            funnel.reject(decision.reason)

        score = opportunity_score(
            net_profit,
            net_roi,
            density,
            75.0,
            stress_profit,
            3,
            0.5,
            0.0,
            decision.execution_status,
        )
        row = proof.to_dict()
        row.update(
            {
                "engine_version": "Opportunity Engine V3",
                "policy_stage": decision.stage,
                "confidence_class": decision.confidence_class,
                "mail_eligible": decision.mail_eligible,
                "policy_reason": decision.reason,
                "execution_status": decision.execution_status,
                "opportunity_score": score,
                "score_grade": score_grade(score),
            }
        )
        rows.append(row)

    funnel.stage("final_rows", len(rows))
    funnel.stage("formal_mail", sum(1 for r in rows if bool(r.get("mail_eligible"))))
    stage_order = {"MAIL": 0, "SAFE": 1, "WATCH": 2, "RESEARCH": 3, "DANGER": 4}
    rows.sort(
        key=lambda r: (
            stage_order.get(str(r.get("policy_stage")), 9),
            -float(r.get("opportunity_score") or 0),
            -float(r.get("net_profit") or 0),
        )
    )
    pd.DataFrame(rows[:TOP]).to_csv(RESULT, index=False)
    funnel.write_json(FUNNEL_PATH)

    lines = [
        f"# V3 {SOURCE_LABEL} contract opportunities",
        "",
        f"- Structure: {STRUCTURE_ID}",
        f"- Contract snapshot: {c_modified}",
        f"- Jita market snapshot: {m_modified}",
        f"- Active plain-item contracts: {len(grouped)}",
        f"- Deep-validation contracts: {len(selected)}",
        f"- Final rows: {len(rows[:TOP])}",
        f"- Formal MAIL: {sum(1 for r in rows if bool(r.get('mail_eligible')))}",
        "",
        "Authenticated structure access is treated as verified.",
        "Each contract chooses the better executable exit between local structure BUY depth and Jita 4-4 BUY depth.",
        "Jita exits include a configurable hauling reserve; local exits do not.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", "utf-8")
    print(
        f"V3 structure contracts done: {SOURCE_LABEL} active={len(grouped)} "
        f"rows={len(rows[:TOP])} mail={sum(1 for r in rows if bool(r.get('mail_eligible')))}"
    )


if __name__ == "__main__":
    main()
