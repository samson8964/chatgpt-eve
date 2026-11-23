"""Independent research scanner for PLEX-containing celebration crates.

Consumes the most recent *complete* V4 public snapshot, refreshes all active
private structure books with existing ESI permissions, and ranks twenty market
and public item-exchange contract opportunities together. No live trade claims.
Does not change V4 scanning, valuation, SQLite, cleanup or mail schedules.

By default this command only prints results. Game mail is separately gated.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from v4.engine import Order, Policy, fill_book
from v4.structure_registry import STRUCTURES
from v4.catalog import Catalog, DEFAULT_CACHE
from v4.sources import market_dataframe, contract_dataframes

JITA = 60003760
PLEX = 44992
RANDOM_ISK = 15_000_000
TAX = Policy().sales_tax
COMPLETE_GATE = "INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED"
# Each guaranteed amount is verified in EVE Ref's type description.
# Random crates have no guaranteed PLEX; use the explicitly requested
# 15m ISK *research assumption* only, not a redeemable floor.
BOXES = {
    80240: ("Yoiul Festival Celebration Crate", 20),
    95463: ("Federation Day Celebration Crate", 10),
    95657: ("Liberation Day Celebration Crate", 10),
    95747: ("Foundation Day Celebration Crate", 10),
    96336: ("Union Day Celebration Crate", 10),
    97649: ("Totality Day Celebration Crate", 10),
    91196: ("200 PLEX and Rare SKINR Supplies Crate", 200),
    91197: ("500 PLEX and Rare SKINR Supplies Crate", 500),
    91198: ("1000 PLEX and Rare SKINR Supplies Crate", 1000),
    91199: ("1500 PLEX and Rare SKINR Supplies Crate", 1500),
    97314: ("YC128 Shifting-Spacetime Crate", 0),
    78889: ("Mysterious GalNet Crate", 0),
    79186: ("Mysterious GalNet Crate II", 0),
}
MAX_GAME_BODY = 9000


def _positive(value, *, zero=False):
    try:
        n = float(value)
        return n if math.isfinite(n) and (n >= 0 if zero else n > 0) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _int(value):
    try:
        n = int(value)
        return n if str(value).strip() not in ("True", "False") else None
    except (ValueError, TypeError, OverflowError):
        return None


def _json(path):
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def _time(value):
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return t if t.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def latest_complete_run(root, *, max_age_minutes=150, now=None):
    """Never skip an incomplete newest run to silently reuse a good old one."""
    now = now or datetime.now(timezone.utc)
    dirs = sorted((p for p in (Path(root) / "runs").iterdir()
                   if p.is_dir() and (p / "manifest.json").is_file()), reverse=True)
    if not dirs:
        raise RuntimeError("CRATE_NO_V4_RUN")
    folder = dirs[0]
    manifest = _json(folder / "manifest.json")
    if not (manifest.get("status") == "SHADOW_RECORDED"
            and manifest.get("coverage_gate") == COMPLETE_GATE
            and manifest.get("source_input_integrity") == "ALL_PARSED"
            and not manifest.get("failed_structure_lanes")):
        raise RuntimeError("CRATE_V4_SOURCE_NOT_COMPLETE")
    if any(r.get("status") != "COMPLETE"
           for r in (manifest.get("structure_health") or {}).values()):
        raise RuntimeError("CRATE_V4_STRUCTURE_INCOMPLETE")
    end = _time(manifest.get("finished_at"))
    if not end or not 0 <= (now - end).total_seconds() <= max_age_minutes * 60:
        raise RuntimeError("CRATE_SOURCE_STALE")
    for name in ("market_orders.csv.bz2", "public_contracts.tar.bz2"):
        if not (folder / "source" / name).is_file():
            raise RuntimeError("CRATE_SOURCE_FILE_MISSING")
    return folder, manifest


def _orders(rows):
    out = []
    for row in rows:
        try:
            out.append(Order.parse(row))
        except (TypeError, ValueError, KeyError, OverflowError):
            if _positive(row.get("volume_remain"), zero=True) == 0:
                continue  # non-tradable residual, never priced
            raise RuntimeError("CRATE_RELEVANT_MARKET_ORDER_INVALID") from None
    return out


def _books(orders):
    books = defaultdict(list)
    for o in orders:
        books[(o.location_id, o.type_id, o.buy)].append(o)
    for key, rows in books.items():
        rows.sort(key=lambda r: (-r.price if r.buy else r.price, r.order_id))
    return books


def _cash_out(box_counts, other_counts, books, *, tax=TAX):
    plex_units = sum(BOXES[t][1] * q for t, q in box_counts.items())
    plex_units += other_counts.get(PLEX, 0)
    random_units = sum(q for t, q in box_counts.items() if BOXES[t][1] == 0)
    cash = random_units * RANDOM_ISK
    missing = []
    if plex_units:
        filled = fill_book(books.get((JITA, PLEX, True), []), plex_units)
        if filled.units != plex_units:
            return None  # Never substitute a PLEX ask or regional reference.
        cash += filled.value
    for tid, qty in other_counts.items():
        if tid == PLEX or qty <= 0:
            continue
        filled = fill_book(books.get((JITA, tid, True), []), qty)
        if filled.units == qty:
            cash += filled.value
        else:
            missing.append(tid)  # No confirmed liquidity -> zero credited.
    return {"gross": cash, "net_after_tax": cash * (1 - tax),
            "guaranteed_plex": plex_units, "random_boxes": random_units,
            "unpriced_other_types": missing}


def _evaluate_market(books, locations, catalog, haul_fn, *, tax=TAX):
    found = []
    for loc in locations:
        if loc == JITA:
            continue  # A Jita sell offer is not inter-station arbitrage.
        for tid, (name, guaranteed) in BOXES.items():
            asks = books.get((loc, tid, False), [])
            if not asks:
                continue
            unit_volume = _positive(catalog.volume(tid))
            if unit_volume is None:
                continue
            # Optimize against both ask step changes and PLEX buy-depth steps.
            end_points = set()
            running = 0
            for o in asks:
                running += o.remaining
                end_points.add(running)
            if guaranteed:
                bid_units = 0
                for b in books.get((JITA, PLEX, True), []):
                    bid_units += b.remaining
                    n = bid_units // guaranteed
                    if 0 < n <= running:
                        end_points.add(n)
            best = None
            for n in sorted(end_points):
                spend = fill_book(asks, n)
                if spend.units != n:
                    continue
                cash = _cash_out({tid: n}, {}, books, tax=tax)
                if cash is None:
                    continue
                freight = _positive(haul_fn(loc, unit_volume * n), zero=True)
                if freight is None:
                    continue
                capital = spend.value + freight
                profit = cash["net_after_tax"] - capital
                if capital <= 0 or profit <= 0:
                    continue
                record = {"kind": "market", "source_location": loc,
                          "type_id": tid, "type_name": name, "quantity": n,
                          "gross_isk": cash["gross"], "purchase_isk": spend.value,
                          "haul_isk": freight, "net_profit_isk": profit,
                          "roi": profit / capital, "capital_isk": capital,
                          "guaranteed_plex": cash["guaranteed_plex"],
                          "random_boxes": cash["random_boxes"],
                          "ask_order_ids": list(spend.order_ids),
                          "value_basis": ("GUARANTEED_PLEX_JITA_BID_DEPTH" if guaranteed
                                          else "USER_ASSUMED_RANDOM_CRATE_15M")}
                if best is None or record["net_profit_isk"] > best["net_profit_isk"]:
                    best = record
            if best is not None:
                found.append(best)
    return found


def _evaluate_contracts(contracts, items, books, locations, catalog, haul_fn,
                        *, now=None, tax=TAX):
    now = now or datetime.now(timezone.utc)
    included = defaultdict(lambda: defaultdict(int))
    requested = set()
    for row in items:
        cid, tid, qty = _int(row.get("contract_id")), _int(row.get("type_id")), _int(row.get("quantity"))
        if cid is None or tid is None or qty is None or qty <= 0:
            continue
        if str(row.get("is_included")).strip().lower() not in ("true", "1", "t"):
            requested.add(cid)
        else:
            included[cid][tid] += qty
    found = []
    for c in contracts:
        cid, loc = _int(c.get("contract_id")), _int(c.get("start_location_id"))
        if cid is None or loc not in locations or cid in requested:
            continue
        if str(c.get("type", "")).lower() != "item_exchange":
            continue
        if str(c.get("status", "outstanding")).lower() not in ("outstanding", ""):
            continue
        expires = _time(c.get("date_expired"))
        if expires and expires < now:
            continue
        price = _positive(c.get("price"), zero=True)
        all_goods = included.get(cid, {})
        boxes = {tid: q for tid, q in all_goods.items() if tid in BOXES and q > 0}
        if price is None or not boxes:
            continue
        other = {tid: q for tid, q in all_goods.items()
                 if tid not in BOXES and catalog.classification(tid) != "blueprint_type"}
        cash = _cash_out(boxes, other, books, tax=tax)
        if cash is None:
            continue
        # Transport only the credited cargo. Unpriced or blueprint items receive
        # no value and are not presumed moved; full contract price paid once.
        credited = {**boxes}
        for tid, qty in other.items():
            if tid not in cash["unpriced_other_types"]:
                credited[tid] = qty
        cargo = 0.0
        for tid, qty in credited.items():
            volume = _positive(catalog.volume(tid))
            if volume is None:
                cargo = None
                break
            cargo += volume * qty
        if cargo is None:
            continue
        freight = _positive(haul_fn(loc, cargo), zero=True)
        if freight is None:
            continue
        capital = price + freight
        if capital <= 0:  # Free contract still needs explicit handling.
            continue
        profit = cash["net_after_tax"] - capital
        if profit <= 0:
            continue
        found.append({
            "kind": "contract", "contract_id": cid, "source_location": loc,
            "contract_title": str(c.get("title") or "")[:100],
            "included_box_types": {str(k): v for k, v in boxes.items()},
            "other_type_count": len(other),
            "other_credited_count": len(other) - len(cash["unpriced_other_types"]),
            "unpriced_other_types": cash["unpriced_other_types"][:10],
            "gross_isk": cash["gross"], "purchase_isk": price,
            "haul_isk": freight, "net_profit_isk": profit,
            "capital_isk": capital, "roi": profit / capital,
            "guaranteed_plex": cash["guaranteed_plex"],
            "random_boxes": cash["random_boxes"],
            "value_basis": "PLEX_BIDS_PLUS_OTHER_JITA_BIDS_OR_15M_RANDOM",
        })
    return found


def rank_opportunities(orders, contracts, items, *, locations, catalog, haul_fn, now=None):
    """Pure evaluator, easy to fixture-test without touching ESI or mail."""
    books = _books(orders)
    markets = _evaluate_market(books, locations, catalog, haul_fn)
    bundles = _evaluate_contracts(contracts, items, books, locations, catalog,
                                  haul_fn, now=now)
    combined = markets + bundles
    combined.sort(key=lambda r: (-r["net_profit_isk"], -r["roi"],
                                 r["kind"], r.get("contract_id", r.get("type_id", 0))))
    return {"top20": combined[:20], "examined": len(combined),
            "market_profitable": len(markets),
            "contract_profitable": len(bundles)}


def _source_rows(folder, locations):
    contracts, items = contract_dataframes(folder / "source" / "public_contracts.tar.bz2")
    if "is_included" not in items.columns:
        raise RuntimeError("CRATE_CONTRACT_INCLUSION_FLAG_MISSING")
    contracts = contracts[contracts["start_location_id"].isin(locations)]
    items = items[items["contract_id"].isin(set(contracts["contract_id"]))]
    # Filter by a crate before reading the massive order book. A bundle's
    # other item types must still be priced against the full Jita depth.
    crate_cids = set(items.loc[items["type_id"].isin(BOXES), "contract_id"])
    contracts = contracts[contracts["contract_id"].isin(crate_cids)]
    items = items[items["contract_id"].isin(crate_cids)]
    needed = set(BOXES) | {PLEX} | set(items["type_id"].dropna().astype(int))
    raw = market_dataframe(folder / "source" / "market_orders.csv.bz2")
    raw = raw[raw["type_id"].isin(needed)]
    return contracts.to_dict("records"), items.to_dict("records"), raw.to_dict("records"), needed


def scan(root, *, fetch_structures=None, max_age_minutes=150):
    """One on-demand full check, isolated from production tasks and databases."""
    from v4.deep_scan import WORKER, request, known_station_regions, haul
    from v4.local_run import deep_scan_environment
    from v4.structure_transport import all_structure_orders
    from v4.npc_station_catalog import load_catalog
    from v4.deep_scan import KNOWN_STATIONS
    folder, manifest = latest_complete_run(root, max_age_minutes=max_age_minutes)
    catalog = Catalog.load(DEFAULT_CACHE)
    npc = load_catalog(root)
    npc_stations = {int(k): v for k, v in (npc or {}).get("stations", {}).items()}
    private_locs = {loc for loc, _ in STRUCTURES.values()}
    market_locs = private_locs | set(KNOWN_STATIONS.values())
    contract_locs = market_locs | set(npc_stations)
    contracts, items, public, needed = _source_rows(folder, contract_locs)
    if fetch_structures is None:
        key = deep_scan_environment().get("EVE_MARKET_API_KEY")
        if not key:
            raise RuntimeError("CRATE_BRIDGE_CREDENTIAL_MISSING")
        private, health = all_structure_orders(
            key, structures=STRUCTURES, worker=WORKER, fetch=request)
    else:
        private, health = fetch_structures()
    if set(health) != set(STRUCTURES) or any(
            d.get("status") != "COMPLETE" for d in health.values()):
        raise RuntimeError("CRATE_STRUCTURE_PAGINATION_INCOMPLETE")
    filtered_private = [r for r in private if _int(r.get("type_id")) in needed]
    orders = _orders(public + filtered_private)
    station_regions = known_station_regions()
    def freight(src, volume):
        return haul(src, JITA, volume, station_regions, npc_stations)
    # Contracts use the extended NPC scope, market offers stay with V4's
    # existing named NPC hubs and the six active private structures.
    market_only = [o for o in orders if o.location_id in market_locs
                   or (o.location_id == JITA and o.buy)]
    market_books = _books(market_only)
    market = _evaluate_market(market_books, market_locs, catalog, freight)
    contracts_found = _evaluate_contracts(
        contracts, items, _books(orders), contract_locs, catalog, freight)
    rows = sorted(market + contracts_found,
                  key=lambda x: (-x["net_profit_isk"], -x["roi"],
                                 x["kind"], x.get("contract_id", x.get("type_id", 0))))
    return {"schema": 1, "status": "SNAPSHOT_RESEARCH_ONLY",
            "source_run": folder.name, "generated_at": datetime.now(timezone.utc).isoformat(),
            "coverage_gate": manifest["coverage_gate"],
            "structure_pages": {k: v.get("pages_fetched") for k, v in health.items()},
            "market_profitable": len(market),
            "contract_profitable": len(contracts_found),
            "total_profitable": len(rows), "top20": rows[:20],
            "random_crate_assumption_isk": RANDOM_ISK,
            "sales_tax_rate": TAX,
            "limitations": ["Snapshot bids are not executable quotes",
                            "Random crates assumed 15m ISK; not guaranteed payout",
                            "Contract access, price, transport and orders not live revalidated"]}


def _money(n):
    return f"{n / 1e8:.2f}亿" if n >= 1e8 else f"{n / 1e4:.1f}万"


def format_game_mail(result, names=None):
    names = names or {}
    types = names.get("types") or {}
    stations = names.get("stations") or {}
    title = f"礼盒套利待核 {len(result['top20'])}条｜市场+合同"
    lines = ["【独立礼盒研究｜收益前20】",
             "固定PLEX按吉他买单深度；随机箱按1500万/箱假设；均非可成交报价。"]
    for idx, row in enumerate(result["top20"], 1):
        loc = html.escape(stations.get(str(row["source_location"]), str(row["source_location"])))
        if row["kind"] == "market":
            tid = row["type_id"]
            name = html.escape(types.get(str(tid), BOXES[tid][0]))
            link = f"<url=showinfo:{tid}>{name}</url>"
            info = f"市场 {link}×{row['quantity']}"
        else:
            cid = row["contract_id"]
            names_list = [types.get(str(t), BOXES[int(t)][0])
                          for t in row["included_box_types"]]
            label = html.escape("、".join(names_list[:2]) + ("等" if len(names_list) > 2 else ""))
            info = f"合同 <url=contract:0//{cid}>{label}</url>"
        lines.append(f"{idx}. {info}｜{loc}")
        lines.append(f"净利{_money(row['net_profit_isk'])} ROI{row['roi'] * 100:.1f}%"
                     f"｜买入{_money(row['purchase_isk'])} 运费{_money(row['haul_isk'])}"
                     f"｜PLEX {row['guaranteed_plex']} 随机箱{row['random_boxes']}")
        if row.get("unpriced_other_types"):
            lines.append("未计价的其他商品类型数：" +
                         str(row["other_type_count"] - row["other_credited_count"]))
    lines.append("快照研究，合同/市场可变，买前人工复核；未计入随机奖励实际期望。")
    body = "<br>".join(lines)
    if len(body) > MAX_GAME_BODY:
        raise RuntimeError("CRATE_GAME_MAIL_TOO_LONG")
    return title, body


def send_to_existing_recipients(root, result, *, transport=None):
    """Separate idempotent receipts; never call the V4 formal mail scheduler."""
    from v4.game_mail_review import read_settings, EXPECTED_SENDER_ID
    from v4.eve_mail_test import WORKER_URL, _get_bridge_credential, _request_json
    from v4.mail_names import load as load_names
    from requests import Session
    settings = read_settings(root)
    if not settings or not settings.get("recipients"):
        raise RuntimeError("CRATE_GAME_RECIPIENTS_NOT_CONFIGURED")
    if result.get("status") != "SNAPSHOT_RESEARCH_ONLY":
        raise RuntimeError("CRATE_RESULT_NOT_VERIFIED")
    title, body = format_game_mail(result, load_names(root))
    client = transport or Session()
    headers = {"Authorization": "Bearer " + _get_bridge_credential(),
               "User-Agent": "EVE independent crate research", "Content-Type": "application/json"}
    status, health = _request_json(client, "GET", WORKER_URL + "/api/mail-health",
                                   headers=headers, timeout=30)
    if status != 200 or not health.get("ok") or health.get("sender_id") != EXPECTED_SENDER_ID:
        raise RuntimeError("CRATE_GAME_MAIL_SENDER_NOT_VERIFIED")
    receipts = Path(root) / "crate-radar" / "mail-receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    results = []
    for rec in settings["recipients"]:
        rid = int(rec["id"])
        path = receipts / f"{result['source_run']}-{rid}.json"
        if path.is_file():
            results.append({"recipient": rec["name"], "status": "ALREADY_SENT"})
            continue
        idem = "v4-crate-radar:" + hashlib.sha256(
            f"{result['source_run']}|{rid}|crate-radar-v1".encode()).hexdigest()[:38]
        status, out = _request_json(client, "POST", WORKER_URL + "/api/send-mail",
                                    headers=headers, json={
                                        "recipient_id": rid, "subject": title,
                                        "body": body, "idempotency_key": idem}, timeout=80)
        if status != 200 or out.get("ok") is not True:
            results.append({"recipient": rec["name"], "status": "FAILED",
                            "http_status": status})
            continue
        skipped = out.get("skipped") is True
        if skipped and out.get("reason") != "duplicate":
            results.append({"recipient": rec["name"], "status": "UNVERIFIED_SKIP"})
            continue
        if not skipped and (out.get("sender_id") != EXPECTED_SENDER_ID or
                            out.get("recipient_id") != rid or
                            _int(out.get("mail_id")) is None):
            results.append({"recipient": rec["name"], "status": "BAD_WORKER_RECEIPT"})
            continue
        record = {"run": result["source_run"], "recipient_id": rid,
                  "recipient": rec["name"], "mail_id": out.get("mail_id"),
                  "accepted": True, "skipped_duplicate": skipped,
                  "sent_at": datetime.now(timezone.utc).isoformat()}
        tmp = path.with_suffix(".part")
        try:
            tmp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
        results.append({"recipient": rec["name"], "status": "ACCEPTED"})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path.home() / "EVE-V4-Data")
    parser.add_argument("--send-game", action="store_true")
    parser.add_argument("--confirm-research-only", action="store_true")
    args = parser.parse_args()
    if args.send_game and not args.confirm_research_only:
        parser.error("--send-game requires --confirm-research-only")
    result = scan(args.data_root)
    if args.send_game:
        result["delivery"] = send_to_existing_recipients(args.data_root, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
