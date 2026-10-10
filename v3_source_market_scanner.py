from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from contract_deal_scanner import SALES_TAX_RATE
from opportunity_engine_v2 import (
    drop_best_price_level,
    opportunity_score,
    profit_density,
    score_grade,
)
from opportunity_engine_v3 import fetch_live_jita_books
from scanner_source import (
    DATA,
    ESI,
    JITA_SYSTEM,
    LATEST,
    MARKET_ORDERS_INDEX,
    download,
    fetch_many_ref,
    get_json,
    latest_file,
    load_market_orders,
    name_en,
    prepare_jita_books,
    truthy_series,
    type_volume,
)
from v3_engine import ExecutionProof, PolicyConfig, RejectionFunnel, evaluate_execution

SOURCE_KIND = (os.getenv("V3_SOURCE_KIND", "npc") or "npc").strip().lower()
SOURCE_KEY = (os.getenv("V3_SOURCE_KEY", "source") or "source").strip().lower().replace(" ", "_")
SOURCE_LABEL = (os.getenv("V3_SOURCE_LABEL", SOURCE_KEY) or SOURCE_KEY).strip()
REGION_ID = int(os.getenv("V3_SOURCE_REGION_ID", "0") or 0)
STATION_ID = int(os.getenv("V3_SOURCE_STATION_ID", "0") or 0)
STRUCTURE_ID = int(os.getenv("SOURCE_STRUCTURE_ID", "0") or 0)
LIVE_LIMIT = int(os.getenv("V3_SOURCE_LIVE_LIMIT", "180"))
TOP = int(os.getenv("V3_SOURCE_TOP", "120"))
PREFILTER_MIN_PROFIT = float(os.getenv("V3_SOURCE_PREFILTER_MIN_PROFIT", "5000000"))
PREFILTER_MIN_ROI = float(os.getenv("V3_SOURCE_PREFILTER_MIN_ROI", "0.03"))
HAUL_BASE = float(os.getenv("V3_SOURCE_HAUL_BASE", os.getenv("DEAL_HAUL_BASE_ISK", "2000000")))
HAUL_PER_M3 = float(os.getenv("V3_SOURCE_HAUL_ISK_PER_M3", "0"))
HAUL_PER_M3_JUMP = float(os.getenv("V3_SOURCE_HAUL_ISK_PER_M3_JUMP", os.getenv("DEAL_HAUL_ISK_PER_M3_JUMP", "200")))
FIXED_JUMPS = int(os.getenv("V3_SOURCE_JUMPS_TO_JITA", "-1"))

RESULT = LATEST / os.getenv("V3_SOURCE_RESULT_CSV", f"v3_{SOURCE_KEY}_to_jita.csv")
REPORT = LATEST / os.getenv("V3_SOURCE_REPORT_MD", f"v3_{SOURCE_KEY}_to_jita.md")
FUNNEL_PATH = LATEST / os.getenv("V3_SOURCE_FUNNEL_JSON", f"v3_{SOURCE_KEY}_to_jita_funnel.json")


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "t", "yes", "y"}


def build_station_sells(orders: pd.DataFrame, region_id: int, station_id: int) -> dict[int, list[dict]]:
    if orders.empty or region_id <= 0 or station_id <= 0:
        return {}
    loc_col = "location_id" if "location_id" in orders.columns else "station_id"
    buy = truthy_series(orders["is_buy_order"])
    common = orders["region_id"].eq(region_id) & orders[loc_col].eq(station_id) & ~buy
    cols = ["type_id", "price", "volume_remain", "min_volume"]
    df = orders.loc[common, cols].copy()
    if df.empty:
        return {}
    df["type_id"] = pd.to_numeric(df["type_id"], errors="coerce").fillna(0).astype(int)
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0.0)
    df["volume_remain"] = pd.to_numeric(df["volume_remain"], errors="coerce").fillna(0).astype(int)
    df["min_volume"] = pd.to_numeric(df["min_volume"], errors="coerce").fillna(1).astype(int)
    df = df[(df["type_id"] > 0) & (df["price"] > 0) & (df["volume_remain"] > 0)]
    df.sort_values(["type_id", "price"], ascending=[True, True], inplace=True)
    out: dict[int, list[dict]] = {}
    for r in df.itertuples(index=False):
        out.setdefault(int(r.type_id), []).append(
            {"price": float(r.price), "vol": int(r.volume_remain), "min": max(1, int(r.min_volume))}
        )
    return out


def _fetch_npc_book(type_id: int) -> tuple[int, list[dict], str | None]:
    rows: list[dict] = []
    page = 1
    try:
        while True:
            payload, headers = get_json(
                f"{ESI}/markets/{REGION_ID}/orders/",
                params={
                    "datasource": "tranquility",
                    "order_type": "sell",
                    "type_id": int(type_id),
                    "page": page,
                },
                timeout=35,
                tries=3,
            )
            for row in payload or []:
                if int(row.get("location_id") or 0) != STATION_ID or _truthy(row.get("is_buy_order")):
                    continue
                price = float(row.get("price") or 0.0)
                vol = int(row.get("volume_remain") or 0)
                if price <= 0 or vol <= 0:
                    continue
                rows.append(
                    {
                        "price": price,
                        "vol": vol,
                        "min": max(1, int(row.get("min_volume") or 1)),
                        "order_id": int(row.get("order_id") or 0),
                    }
                )
            pages = max(1, int(headers.get("X-Pages") or 1))
            if page >= pages:
                break
            page += 1
        rows.sort(key=lambda x: (x["price"], x.get("order_id", 0)))
        return int(type_id), rows, None
    except Exception as exc:
        return int(type_id), [], str(exc)


def fetch_live_npc_sells(type_ids: list[int]) -> tuple[dict[int, list[dict]], set[int], str]:
    ids = sorted({int(x) for x in type_ids if int(x) > 0})
    if not ids:
        return {}, set(), datetime.now(timezone.utc).isoformat()
    out: dict[int, list[dict]] = {}
    failed: set[int] = set()
    workers = min(max(1, int(os.getenv("V3_LIVE_WORKERS", "14"))), len(ids))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_fetch_npc_book, tid): tid for tid in ids}
        for fut in as_completed(futs):
            tid = futs[fut]
            try:
                rt, book, err = fut.result()
            except Exception:
                failed.add(tid)
                continue
            out[rt] = book
            if err:
                failed.add(rt)
    return out, failed, datetime.now(timezone.utc).isoformat()


def load_structure_sells() -> tuple[dict[int, list[dict]], str]:
    if STRUCTURE_ID <= 0:
        raise RuntimeError("SOURCE_STRUCTURE_ID is required for structure source")
    from structure_market_arbitrage import load_structure_sells as _load

    books, _, expires = _load()
    return books, str(expires or "")


def route_jumps_to_jita() -> int:
    if FIXED_JUMPS >= 0:
        return FIXED_JUMPS
    if SOURCE_KIND != "npc" or STATION_ID <= 0:
        return 0
    try:
        station, _ = get_json(f"{ESI}/universe/stations/{STATION_ID}/", timeout=25, tries=3)
        origin = int(station.get("system_id") or 0)
        if origin <= 0:
            return 0
        route, _ = get_json(
            f"{ESI}/route/{origin}/{JITA_SYSTEM}/",
            params={"datasource": "tranquility", "flag": "secure"},
            timeout=25,
            tries=3,
        )
        return max(0, len(route or []) - 1)
    except Exception:
        return 0


def haul_cost(total_m3: float, jumps: int) -> float:
    return max(0.0, HAUL_BASE) + max(0.0, total_m3) * (
        max(0.0, HAUL_PER_M3) + max(0, jumps) * max(0.0, HAUL_PER_M3_JUMP)
    )


def match_books(asks: list[dict], bids: list[dict], *, min_marginal_roi: float = 0.0) -> dict | None:
    if not asks or not bids:
        return None
    ai = bi = 0
    ask_left = int(asks[0].get("vol", 0))
    bid_left = int(bids[0].get("vol", 0))
    qty = 0
    source_cost = 0.0
    destination_gross = 0.0
    first_ask = float(asks[0]["price"])
    first_bid = float(bids[0]["price"])
    worst_ask = first_ask
    worst_bid = first_bid

    while ai < len(asks) and bi < len(bids):
        ask = asks[ai]
        bid = bids[bi]
        ask_price = float(ask["price"])
        bid_price = float(bid["price"])
        net_bid = bid_price * (1.0 - SALES_TAX_RATE)
        marginal_roi = (net_bid - ask_price) / max(ask_price, 1e-9)
        if marginal_roi < min_marginal_roi:
            break

        take = min(ask_left, bid_left)
        if take <= 0:
            break
        bid_min = max(1, int(bid.get("min", 1)))
        if take < bid_min:
            bi += 1
            if bi < len(bids):
                bid_left = int(bids[bi].get("vol", 0))
            continue

        qty += take
        source_cost += ask_price * take
        destination_gross += bid_price * take
        worst_ask = ask_price
        worst_bid = bid_price
        ask_left -= take
        bid_left -= take

        if ask_left <= 0:
            ai += 1
            if ai < len(asks):
                ask_left = int(asks[ai].get("vol", 0))
        if bid_left <= 0:
            bi += 1
            if bi < len(bids):
                bid_left = int(bids[bi].get("vol", 0))

    if qty <= 0 or source_cost <= 0:
        return None
    tax = destination_gross * SALES_TAX_RATE
    before_haul = destination_gross - tax - source_cost
    return {
        "quantity": qty,
        "source_cost": source_cost,
        "destination_gross": destination_gross,
        "sales_tax": tax,
        "net_before_haul": before_haul,
        "net_roi_before_haul": before_haul / source_cost,
        "source_best_sell": first_ask,
        "source_worst_sell": worst_ask,
        "jita_best_buy": first_bid,
        "jita_worst_buy": worst_bid,
    }


def select_candidate_ids(rows: list[dict], limit: int) -> list[int]:
    if not rows or limit <= 0:
        return []
    by_profit = sorted(rows, key=lambda r: float(r.get("net_before_haul", -math.inf)), reverse=True)
    by_roi = sorted(rows, key=lambda r: float(r.get("net_roi_before_haul", -math.inf)), reverse=True)
    chosen: dict[int, None] = {}
    profit_quota = max(1, int(limit * 0.7))
    roi_quota = max(1, limit - profit_quota)
    for row in by_profit[:profit_quota]:
        chosen[int(row["type_id"])] = None
    for row in by_roi[:roi_quota]:
        chosen[int(row["type_id"])] = None
    for row in by_profit:
        if len(chosen) >= limit:
            break
        chosen.setdefault(int(row["type_id"]), None)
    return list(chosen)[:limit]


def select_trade_quote(
    asks: list[dict], bids: list[dict], *, unit_m3: float, jumps: int, cfg: PolicyConfig
) -> tuple[dict | None, float]:
    """Avoid diluting profitable small fills with marginal low-ROI depth.

    Evaluate full positive spread and two stricter marginal-ROI cutoffs. The
    formal profit/ROI/density/stress gates remain unchanged; only trade size
    selection improves. Stress always uses the same cutoff as the chosen fill.
    """
    stress_asks = drop_best_price_level(asks)
    stress_bids = drop_best_price_level(bids)
    best_quote, best_cutoff, best_rank = None, 0.0, None
    for cutoff in sorted({0.0, cfg.mail_min_roi, cfg.mail_min_roi + 0.05}):
        q = match_books(asks, bids, min_marginal_roi=cutoff)
        if not q:
            continue
        volume = unit_m3 * int(q["quantity"])
        transport = haul_cost(volume, jumps)
        net = q["net_before_haul"] - transport
        roi = net / (q["source_cost"] + transport) if q["source_cost"] + transport > 0 else 0.0
        density = profit_density(net, volume)
        stressed = match_books(stress_asks, stress_bids, min_marginal_roi=cutoff)
        stress_net = (
            stressed["net_before_haul"] - haul_cost(unit_m3 * int(stressed["quantity"]), jumps)
            if stressed else -1.0
        )
        formal = (
            net >= cfg.mail_min_profit and roi >= cfg.mail_min_roi
            and density >= cfg.min_profit_per_m3 and stress_net > 0
        )
        rank = (int(formal), int(stress_net > 0), net)
        if best_rank is None or rank > best_rank:
            best_quote, best_cutoff, best_rank = q, cutoff, rank
    return best_quote, best_cutoff


def main() -> None:
    LATEST.mkdir(parents=True, exist_ok=True)
    funnel = RejectionFunnel()
    cfg = PolicyConfig.from_env()
    print(f"V3 source market: {SOURCE_LABEL} -> Jita 4-4 (source kind={SOURCE_KIND})")

    market_url, market_modified = latest_file(MARKET_ORDERS_INDEX)
    market_path = DATA / Path(market_url).name
    if not market_path.exists():
        download(market_url, market_path)
    orders = load_market_orders(market_path)
    _, snapshot_jita_buys = prepare_jita_books(orders)

    if SOURCE_KIND == "npc":
        snapshot_source = build_station_sells(orders, REGION_ID, STATION_ID)
        source_live_seed = None
        source_live_at = ""
    elif SOURCE_KIND == "structure":
        snapshot_source, source_live_at = load_structure_sells()
        source_live_seed = snapshot_source
    else:
        raise RuntimeError(f"Unsupported V3_SOURCE_KIND={SOURCE_KIND}")
    del orders

    funnel.stage("source_sell_types", len(snapshot_source))
    prelim: list[dict] = []
    for tid, asks in snapshot_source.items():
        m = match_books(asks, snapshot_jita_buys.get(int(tid), []), min_marginal_roi=0.0)
        if not m:
            continue
        m["type_id"] = int(tid)
        if m["net_before_haul"] < PREFILTER_MIN_PROFIT and m["net_roi_before_haul"] < PREFILTER_MIN_ROI:
            continue
        prelim.append(m)
    funnel.stage("prefilter_candidates", len(prelim))

    candidate_ids = select_candidate_ids(prelim, LIVE_LIMIT)
    funnel.stage("deep_validation_types", len(candidate_ids))
    if not candidate_ids:
        pd.DataFrame().to_csv(RESULT, index=False)
        funnel.write_json(FUNNEL_PATH)
        REPORT.write_text(f"# {SOURCE_LABEL} -> Jita V3\n\nNo candidates.\n", "utf-8")
        return

    meta = fetch_many_ref("types", candidate_ids)
    if SOURCE_KIND == "npc":
        live_source, source_failed, source_live_at = fetch_live_npc_sells(candidate_ids)
    else:
        live_source = {tid: source_live_seed.get(tid, []) for tid in candidate_ids}
        source_failed = {tid for tid in candidate_ids if not live_source.get(tid)}
    live_jita, jita_failed, jita_live_at = fetch_live_jita_books(candidate_ids, "buy")
    jumps = route_jumps_to_jita()

    rows: list[dict] = []
    for tid in candidate_ids:
        if tid in source_failed or tid in jita_failed:
            funnel.reject("LIVE_BOOK_FAILED")
            continue
        asks = live_source.get(tid, [])
        bids = live_jita.get(tid, [])
        unit_m3 = max(0.0, float(type_volume(meta.get(tid)) or 0.0))
        quote, chosen_cutoff = select_trade_quote(
            asks, bids, unit_m3=unit_m3, jumps=jumps, cfg=cfg
        )
        if not quote:
            funnel.reject("NO_EXECUTABLE_DEPTH")
            continue

        total_m3 = unit_m3 * int(quote["quantity"])
        haul = haul_cost(total_m3, jumps)
        net_profit = quote["net_before_haul"] - haul
        invested = quote["source_cost"] + haul
        net_roi = net_profit / invested if invested > 0 else 0.0
        density = profit_density(net_profit, total_m3)

        stress_asks = drop_best_price_level(asks)
        stress_bids = drop_best_price_level(bids)
        stress = match_books(stress_asks, stress_bids, min_marginal_roi=chosen_cutoff)
        if stress:
            stress_m3 = unit_m3 * int(stress["quantity"])
            stress_haul = haul_cost(stress_m3, jumps)
            stress_profit = stress["net_before_haul"] - stress_haul
            stress_value = stress["destination_gross"]
        else:
            stress_profit = -1.0
            stress_value = 0.0

        proof = ExecutionProof(
            opportunity_id=f"{SOURCE_KEY}:{tid}",
            channel="ARBITRAGE",
            source_cost=quote["source_cost"],
            destination_value=quote["destination_gross"],
            sales_tax=quote["sales_tax"],
            haul_cost=haul,
            volume_m3=total_m3,
            source_depth_complete=True,
            destination_depth_complete=True,
            access_verified=True,
            stress_value=stress_value,
            live_timestamp=max(str(source_live_at or ""), str(jita_live_at or "")),
            coverage=1.0,
            net_profit=net_profit,
            net_roi=net_roi,
            stress_net_profit=stress_profit,
            profit_per_m3=density,
            market_change_pct=0.0,
            fatal=False,
            details={
                "source_key": SOURCE_KEY,
                "source_label": SOURCE_LABEL,
                "source_kind": SOURCE_KIND,
                "source_station_id": STATION_ID if SOURCE_KIND == "npc" else STRUCTURE_ID,
                "jumps_to_jita": jumps,
                "quantity": int(quote["quantity"]),
                "chosen_min_marginal_roi": chosen_cutoff,
                "source_best_sell": quote["source_best_sell"],
                "source_worst_matched_sell": quote["source_worst_sell"],
                "jita_best_buy": quote["jita_best_buy"],
                "jita_worst_matched_buy": quote["jita_worst_buy"],
                "item_name": name_en(meta.get(tid), str(tid)),
                "type_id": tid,
            },
        )
        decision = evaluate_execution(proof, cfg)
        if decision.stage in {"RESEARCH", "WATCH", "DANGER"}:
            funnel.reject(decision.reason)

        score = opportunity_score(
            net_profit,
            net_roi,
            density,
            80.0,
            stress_profit,
            1 if SOURCE_KIND == "npc" else 3,
            max(0.5, jumps / 2 if jumps else 0.5),
            0.0,
            decision.execution_status,
        )
        row = proof.to_dict()
        row.update(
            {
                "engine_version": "Opportunity Engine V3",
                "channel": "SOURCE_TO_JITA",
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
        f"# V3 {SOURCE_LABEL} -> Jita 4-4 procurement arbitrage",
        "",
        f"- Source kind: {SOURCE_KIND}",
        f"- Market snapshot: {market_modified}",
        f"- Secure jumps to Jita: {jumps}",
        f"- Deep-validation types: {len(candidate_ids)}",
        f"- Final rows: {len(rows[:TOP])}",
        f"- Formal MAIL: {sum(1 for r in rows if bool(r.get('mail_eligible')))}",
        "",
        "Destination valuation uses Jita 4-4 BUY orders only. Amarr/Dodixie sell prices are never used as an exit valuation.",
        "Stress removes the best source ask level and best Jita bid level.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", "utf-8")
    print(
        f"V3 source done: {SOURCE_LABEL} candidates={len(candidate_ids)} "
        f"rows={len(rows[:TOP])} mail={sum(1 for r in rows if bool(r.get('mail_eligible')))}"
    )


if __name__ == "__main__":
    main()
