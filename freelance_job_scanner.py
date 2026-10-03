#!/usr/bin/env python3
"""Minimal public EVE Freelance Jobs scanner.

Phase 1 intentionally does not authenticate or accept jobs.
It fetches the public no-ACL pool and ranks jobs using only listing data.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ESI_BASE = "https://esi.evetech.net"
COMPATIBILITY_DATE = os.getenv("ESI_COMPATIBILITY_DATE", "2025-12-16")
USER_AGENT = os.getenv(
    "EVE_USER_AGENT",
    "chatgpt-eve/freelance-jobs-radar (github.com/samson8964/chatgpt-eve)",
)



FORGE_REGION_ID = 10000002
JITA_44_LOCATION_ID = 60003760


def resolve_type(session, type_id):
    return get_json(session, f"/universe/types/{int(type_id)}/")


def jita_sell_orders(session, type_id):
    orders = get_json(session, f"/markets/{FORGE_REGION_ID}/orders/", params={"order_type": "sell", "type_id": int(type_id)})
    return sorted([o for o in orders if int(o.get("location_id", 0)) == JITA_44_LOCATION_ID], key=lambda o: float(o.get("price", 0)))


def executable_cost(orders, quantity):
    need, cost, fills = int(quantity), 0.0, []
    for o in orders:
        if need <= 0:
            break
        take = min(need, int(o.get("volume_remain") or 0))
        if take:
            price = float(o["price"])
            cost += take * price
            fills.append({"quantity": take, "price": price, "order_id": o.get("order_id")})
            need -= take
    return {"fillable": need == 0, "missing": need, "total_cost": cost, "fills": fills}


def resolve_station(session, station_id):
    return get_json(session, f"/universe/stations/{station_id}/")

def resolve_system(session, system_id):
    return get_json(session, f"/universe/systems/{system_id}/")

def transport_risk_estimate(cargo_value, jumps, route_security):
    """Conservative screening cost, not an in-game fee quote."""
    danger = int((route_security or {}).get("danger_systems") or 0)
    low = int((route_security or {}).get("lowsec_systems") or 0)
    null = int((route_security or {}).get("nullsec_systems") or 0)
    base = max(2_000_000.0, cargo_value * 0.0025)
    distance = jumps * max(150_000.0, cargo_value * 0.00015)
    security = cargo_value * (0.015 * low + 0.035 * null)
    return {"base_cost": base, "distance_cost": distance, "security_risk_cost": security, "estimated_total": base + distance + security, "danger_systems": danger}

_TYPE_CACHE = {}
_STATION_CACHE = {}
_SYSTEM_CACHE = {}

def cached_type(session, type_id):
    key = int(type_id)
    if key not in _TYPE_CACHE: _TYPE_CACHE[key] = resolve_type(session, key)
    return _TYPE_CACHE[key]

def cached_station(session, station_id):
    key = int(station_id)
    if key not in _STATION_CACHE: _STATION_CACHE[key] = resolve_station(session, key)
    return _STATION_CACHE[key]

def cached_system(session, system_id):
    key = int(system_id)
    if key not in _SYSTEM_CACHE: _SYSTEM_CACHE[key] = resolve_system(session, key)
    return _SYSTEM_CACHE[key]

def route_security_summary(session, route):
    systems = []
    lowsec = 0
    nullsec = 0
    highsec = 0
    for system_id in route:
        info = cached_system(session, system_id)
        sec = float(info.get("security_status") or 0)
        if sec <= 0.0:
            band = "nullsec"
            nullsec += 1
        elif sec < 0.45:
            band = "lowsec"
            lowsec += 1
        else:
            band = "highsec"
            highsec += 1
        systems.append({"id": system_id, "name": info.get("name"), "security_status": sec, "band": band})
    return {"highsec_systems": highsec, "lowsec_systems": lowsec, "nullsec_systems": nullsec, "danger_systems": lowsec + nullsec, "systems": systems}

def calculate_route(session, origin_system_id, destination_system_id, preference="Shorter"):
    url = f"{ESI_BASE}/route/{origin_system_id}/{destination_system_id}"
    response = session.post(url, json={"preference": preference, "security_penalty": 50}, timeout=45)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        route = payload.get("systems") or payload.get("route") or []
    else:
        route = payload
    return [int(x) for x in route if isinstance(x, (int, str)) and str(x).isdigit()]

def extract_delivery(detail):
    cfg = (((detail.get("configuration") or {}).get("parameters") or {}).get("corporation_item_delivery") or {}).get("corporation_item_delivery") or {}
    type_ids, locations = [], []
    for block in ((cfg.get("item_type") or {}).get("values") or []):
        type_ids.extend(block.get("values") or [])
    for block in ((cfg.get("corporation_office_location") or {}).get("values") or []):
        for value in block.get("values") or []:
            locations.append({"kind": block.get("value_type"), "id": value})
    return type_ids, locations


def get_json(session: requests.Session, path: str, params=None, retries: int = 3):
    url = f"{ESI_BASE}{path}"
    for attempt in range(retries):
        r = session.get(url, params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (420, 429) or 500 <= r.status_code < 600:
            time.sleep(min(2 ** attempt, 8))
            continue
        r.raise_for_status()
    raise RuntimeError(f"ESI request failed after {retries} attempts: {url}")


def fetch_public_jobs(session: requests.Session, limit: int = 100):
    jobs = []
    after = "0"
    seen = set()
    while True:
        payload = get_json(
            session,
            "/freelance-jobs",
            params={"after": after, "limit": limit},
        )
        batch = payload.get("freelance_jobs", [])
        if not batch:
            break
        for job in batch:
            jid = job.get("id")
            if jid and jid not in seen:
                seen.add(jid)
                jobs.append(job)
        cursor = payload.get("cursor") or {}
        nxt = cursor.get("after")
        if not nxt or nxt == after:
            break
        after = str(nxt)
    return jobs


def score(job):
    reward = job.get("reward") or {}
    progress = job.get("progress") or {}
    remaining_reward = float(reward.get("remaining") or 0)
    desired = float(progress.get("desired") or 0)
    current = float(progress.get("current") or 0)
    remaining_work = max(desired - current, 0)
    unit_reward = remaining_reward / remaining_work if remaining_work > 0 else 0
    return (unit_reward, remaining_reward)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--candidates", type=int, default=200, help="Cheap prefilter size before detailed economics")
    ap.add_argument("--raw", default="artifacts/freelance_jobs_raw.json")
    ap.add_argument("--summary", default="artifacts/freelance_jobs_top.json")
    args = ap.parse_args()

    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "en",
            "X-Compatibility-Date": COMPATIBILITY_DATE,
        }
    )

    jobs = fetch_public_jobs(s)
    ranked = sorted(jobs, key=score, reverse=True)
    top = ranked[: max(args.candidates, args.top, 0)]

    Path(args.raw).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    Path(args.raw).write_text(
        json.dumps(
            {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "compatibility_date": COMPATIBILITY_DATE,
                "count": len(jobs),
                "jobs": jobs,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    rows = []
    for j in top:
        reward = j.get("reward") or {}
        progress = j.get("progress") or {}
        remaining_reward = float(reward.get("remaining") or 0)
        remaining_work = max(
            float(progress.get("desired") or 0) - float(progress.get("current") or 0),
            0,
        )
        detail = get_json(s, f"/freelance-jobs/{j.get('id')}") if j.get("id") else {}
        type_ids, delivery_locations = extract_delivery(detail)
        market_checks = []
        for type_id in type_ids:
            type_info = cached_type(s, type_id)
            max_quantity = int(remaining_work) if remaining_work > 0 else 1
            orders = jita_sell_orders(s, type_id)
            unit_reward = float((detail.get("contribution") or {}).get("reward_per_contribution") or 0)
            quantity_options = []
            for quantity in range(1, max_quantity + 1):
                pricing = executable_cost(orders, quantity)
                if not pricing["fillable"]:
                    continue
                cost = pricing["total_cost"]
                gross = unit_reward * quantity
                net = gross - cost
                roi = net / cost if cost > 0 else None
                quantity_options.append({"quantity": quantity, "jita_acquisition_cost": cost, "gross_reward": gross, "gross_spread": net, "gross_roi": roi, "fills": pricing["fills"]})
            best = max(quantity_options, key=lambda x: x["gross_spread"], default=None)
            market_checks.append({"type_id": int(type_id), "type_name": type_info.get("name"), "max_quantity_remaining": max_quantity, "jita_available_quantity_tested": max([x["quantity"] for x in quantity_options], default=0), "best_executable": best, "quantity_options": quantity_options})
        delivery_details = []
        for loc in delivery_locations:
            if loc["kind"] != "station":
                delivery_details.append({"kind": loc["kind"], "id": loc["id"], "status": "HOLD_STRUCTURE_AUTH_REQUIRED"})
                continue
            st = cached_station(s, int(loc["id"]))
            sid = st.get("system_id")
            route = calculate_route(s, 30000142, sid) if sid else []
            security = route_security_summary(s, route) if route else None
            delivery_details.append({"kind": "station", "id": loc["id"], "name": st.get("name"), "system_id": sid, "system_name": cached_system(s, sid).get("name") if sid else None, "jita_shortest_jumps": len(route)-1 if route else None, "route_security": security})
        final_candidates = []
        for mc in market_checks:
            best = mc.get("best_executable")
            if not best: continue
            for dest in delivery_details:
                if dest.get("kind") != "station" or dest.get("jita_shortest_jumps") is None: continue
                risk = transport_risk_estimate(best["jita_acquisition_cost"], dest["jita_shortest_jumps"], dest.get("route_security"))
                adjusted = best["gross_spread"] - risk["estimated_total"]
                adjusted_roi = adjusted / best["jita_acquisition_cost"] if best["jita_acquisition_cost"] > 0 else None
                status = "PASS" if adjusted >= 50_000_000 and adjusted_roi is not None and adjusted_roi >= 0.10 else "REJECT"
                final_candidates.append({"type_id": mc["type_id"], "type_name": mc["type_name"], "quantity": best["quantity"], "destination": dest.get("name"), "destination_system": dest.get("system_name"), "jumps": dest["jita_shortest_jumps"], "acquisition_cost": best["jita_acquisition_cost"], "reward": best["gross_reward"], "gross_spread": best["gross_spread"], "transport_risk_estimate": risk, "risk_adjusted_profit": adjusted, "risk_adjusted_roi": adjusted_roi, "status": status})
        final_status = "PASS" if any(x["status"] == "PASS" for x in final_candidates) else ("HOLD_STRUCTURE_AUTH_REQUIRED" if any(x.get("kind") != "station" for x in delivery_details) and not final_candidates else "REJECT")

        rows.append(
            {
                "id": j.get("id"),
                "name": j.get("name"),
                "state": j.get("state"),
                "reward_remaining": remaining_reward,
                "work_remaining": remaining_work,
                "reward_per_unit_remaining": (
                    remaining_reward / remaining_work if remaining_work > 0 else None
                ),
                "last_modified": j.get("last_modified"),
                "list_record": j,
                "detail": detail,
                "delivery_details": delivery_details,
                "final_candidates": final_candidates,
                "final_status": final_status,
                "execution_screen": {
                    "status": final_status,
                    "note": "Transport risk estimate is a conservative screening model; final opportunity gate must use best executable quantity and route-specific risk.",
                },
                "delivery_locations": delivery_locations,
                "market_checks": market_checks,
            }
        )

    # Final output is ranked by executable risk-adjusted profit, not raw reward.
    for row in rows:
        executable = [x for x in row.get("final_candidates", []) if x.get("risk_adjusted_profit") is not None]
        row["best_risk_adjusted_profit"] = max((x["risk_adjusted_profit"] for x in executable), default=None)
    rows.sort(key=lambda r: (r["best_risk_adjusted_profit"] is not None, r["best_risk_adjusted_profit"] or float("-inf")), reverse=True)
    evaluated_count = len(rows)
    rows = rows[: max(args.top, 0)]

    Path(args.summary).write_text(
        json.dumps(
            {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "public_job_count": len(jobs),
                "evaluated_candidate_count": evaluated_count,
                "top": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"public_job_count": len(jobs), "evaluated_candidate_count": evaluated_count, "top": rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
