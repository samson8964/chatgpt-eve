from __future__ import annotations

import csv
import html
import io
import json
import os
import smtplib
import subprocess
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

import requests

WORKER_URL = os.environ["EVE_TRADE_WORKER_URL"].rstrip("/")
API_KEY = os.environ["EVE_MAIL_API_KEY"]
SMTP_USER = os.environ["GMAIL_SMTP_USER"].strip()
SMTP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"].replace(" ", "").strip()
SMTP_TO = os.environ.get("GMAIL_TO", "").strip() or SMTP_USER
START = datetime.fromisoformat(os.environ.get("TRADE_AUDIT_START", "2026-09-01T00:00:00+00:00").replace("Z", "+00:00"))

PROFILES = ["mikechong", "ladyguagua", "ladybaba"]
DISPLAY = {"mikechong": "MikeChong", "ladyguagua": "LadyGuaGua", "ladybaba": "LadyBaBa"}
FOUR_H = 1053970513596
CJ = 1049588174021
JITA_44 = 60003760

S = requests.Session()
S.headers.update({"Authorization": f"Bearer {API_KEY}", "User-Agent": "chatgpt-eve-private-trade-audit/1.0"})


def parse_dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None


def worker_get(profile: str, resource: str, **params):
    q = {"profile": profile, "resource": resource, **params}
    r = S.get(f"{WORKER_URL}/api/trade-data", params=q, timeout=90)
    if r.status_code != 200:
        raise RuntimeError(f"{DISPLAY[profile]} {resource} read failed HTTP {r.status_code}")
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"{DISPLAY[profile]} {resource} read failed: {data.get('error')}")
    return data


def fetch_transactions(profile: str):
    rows = {}
    from_id = 0
    for _ in range(12):
        payload = worker_get(profile, "transactions", **({"from_id": from_id} if from_id else {}))
        batch = payload.get("data") or []
        if not batch:
            break
        for x in batch:
            rows[int(x["transaction_id"])] = x
        dts = [parse_dt(x.get("date")) for x in batch if x.get("date")]
        if len(batch) < 2500:
            break
        if dts and min(dts) < START:
            break
        new_from = min(int(x["transaction_id"]) for x in batch)
        if new_from == from_id:
            break
        from_id = new_from
    return sorted(rows.values(), key=lambda x: parse_dt(x.get("date")) or START)


def fetch_paged(profile: str, resource: str, max_pages=25):
    first = worker_get(profile, resource, page=1)
    out = list(first.get("data") or [])
    pages = min(int(first.get("pages") or 1), max_pages)
    for p in range(2, pages + 1):
        out.extend(worker_get(profile, resource, page=p).get("data") or [])
    return out


def fetch_contract_items(profile: str, contract_id: int):
    first = worker_get(profile, "contract-items", contract_id=contract_id, page=1)
    out = list(first.get("data") or [])
    pages = min(int(first.get("pages") or 1), 10)
    for p in range(2, pages + 1):
        out.extend(worker_get(profile, "contract-items", contract_id=contract_id, page=p).get("data") or [])
    return out


def git_text(commit: str, path: str):
    p = subprocess.run(["git", "show", f"{commit}:{path}"], capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else ""


def git_commits(path: str, limit=220):
    p = subprocess.run(["git", "log", "--format=%H", f"--since={START.isoformat()}", "--", path], capture_output=True, text=True)
    return [x.strip() for x in p.stdout.splitlines() if x.strip()][:limit]


def csv_rows(text: str):
    if not text.strip():
        return []
    try:
        return list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))
    except Exception:
        return []


def min_dt(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def collect_pushed_opportunities():
    contracts = {}  # contract_id -> {channels,set; first_sent}
    markets = {}    # (location_id,type_id) -> {channels,set; first_sent}

    ph = Path("results/state/mail_push_history.csv")
    if ph.exists():
        for r in csv_rows(ph.read_text(encoding="utf-8-sig")):
            try:
                cid = int(float(r.get("contract_id") or 0))
            except Exception:
                continue
            if cid <= 0:
                continue
            ent = contracts.setdefault(cid, {"channels": set(), "first_sent": None})
            ent["channels"].add(r.get("channel") or "core")
            ent["first_sent"] = min_dt(ent["first_sent"], parse_dt(r.get("last_sent_at")))

    tracked = []
    ls = subprocess.run(["git", "ls-files", "results/state/mail_last_*.csv"], capture_output=True, text=True)
    for path in [x.strip() for x in ls.stdout.splitlines() if x.strip()]:
        base = Path(path).name.lower()
        if "four-h-market" in base:
            tracked.append((path, "market", FOUR_H, "4-H→Jita"))
        elif "cj-market" in base:
            tracked.append((path, "market", CJ, "C-J→Jita"))
        elif "v3-jita-to-4h" in base:
            tracked.append((path, "market", JITA_44, "Jita→4-H"))
        elif "four-h-contract" in base:
            tracked.append((path, "contract", None, "4-H合同"))
        elif "cj-contract" in base:
            tracked.append((path, "contract", None, "C-J合同"))
        elif "v3-cash-floor" in base:
            tracked.append((path, "contract", None, "V3现金底价"))
        elif "v3-barter" in base:
            tracked.append((path, "contract", None, "V3以物易物"))
        elif "v3-conservative-list" in base:
            tracked.append((path, "contract", None, "V3保守挂牌"))
        elif "multi_buyonly" in base:
            tracked.append((path, "contract", None, "多件合同"))

    for path, kind, location, label in tracked:
        for sha in git_commits(path):
            for r in csv_rows(git_text(sha, path)):
                raw_id = r.get("id") or r.get("contract_id")
                try:
                    oid = int(float(raw_id or 0))
                except Exception:
                    continue
                if oid <= 0:
                    continue
                sent = parse_dt(r.get("sent_at") or r.get("updated_at"))
                if kind == "contract":
                    ent = contracts.setdefault(oid, {"channels": set(), "first_sent": None})
                else:
                    ent = markets.setdefault((location, oid), {"channels": set(), "first_sent": None})
                ent["channels"].add(label)
                ent["first_sent"] = min_dt(ent["first_sent"], sent)

    return contracts, markets


def fetch_average_prices():
    r = requests.get("https://esi.evetech.net/latest/markets/prices/?datasource=tranquility", timeout=90,
                     headers={"User-Agent": "chatgpt-eve-private-trade-audit/1.0"})
    r.raise_for_status()
    return {int(x["type_id"]): float(x.get("average_price") or x.get("adjusted_price") or 0) for x in r.json()}


_type_names = {}
def type_name(type_id: int):
    if type_id in _type_names:
        return _type_names[type_id]
    try:
        r = requests.get(f"https://esi.evetech.net/latest/universe/types/{type_id}/?datasource=tranquility", timeout=30,
                         headers={"User-Agent": "chatgpt-eve-private-trade-audit/1.0"})
        if r.ok:
            _type_names[type_id] = r.json().get("name") or str(type_id)
        else:
            _type_names[type_id] = str(type_id)
    except Exception:
        _type_names[type_id] = str(type_id)
    return _type_names[type_id]


def tax_map(journal):
    out = defaultdict(float)
    for j in journal:
        if j.get("context_id_type") != "market_transaction_id":
            continue
        if j.get("ref_type") != "transaction_tax":
            continue
        try:
            tid = int(j.get("context_id") or 0)
            amount = float(j.get("amount") or 0)
        except Exception:
            continue
        if tid:
            out[tid] += amount  # normally negative
    return out


def build_lots(profile, char_id, transactions, journal, contracts_api, pushed_contracts, pushed_markets, avg_prices):
    lots = []
    matched_contracts = []

    # Exact contract-id matches against opportunities that were actually pushed/recorded.
    for c in contracts_api:
        try:
            cid = int(c.get("contract_id") or 0)
            acceptor = int(c.get("acceptor_id") or 0)
        except Exception:
            continue
        if cid not in pushed_contracts or acceptor != int(char_id):
            continue
        status = str(c.get("status") or "")
        if status not in {"finished", "in_progress"}:
            continue
        acquired = parse_dt(c.get("date_completed") or c.get("date_accepted")) or START
        price = float(c.get("price") or 0)
        try:
            items = [x for x in fetch_contract_items(profile, cid) if bool(x.get("is_included", True))]
        except Exception:
            items = []
        grouped = defaultdict(int)
        for x in items:
            try:
                q = int(x.get("quantity") or 0)
                tid = int(x.get("type_id") or 0)
            except Exception:
                continue
            if tid and q > 0:
                grouped[tid] += q

        weights = {}
        if len(grouped) == 1:
            tid = next(iter(grouped))
            weights[tid] = 1.0
        else:
            denom = sum(max(0.0, avg_prices.get(tid, 0.0)) * q for tid, q in grouped.items())
            if denom > 0:
                for tid, q in grouped.items():
                    weights[tid] = (max(0.0, avg_prices.get(tid, 0.0)) * q) / denom
            elif grouped:
                total_q = sum(grouped.values())
                for tid, q in grouped.items():
                    weights[tid] = q / total_q

        for tid, q in grouped.items():
            alloc_cost = price * weights.get(tid, 0)
            lots.append({
                "profile": profile,
                "kind": "contract",
                "source": "+".join(sorted(pushed_contracts[cid]["channels"])),
                "opportunity_id": cid,
                "type_id": tid,
                "date": acquired,
                "quantity": q,
                "unit_cost": alloc_cost / q if q else 0,
                "cost_basis": alloc_cost,
                "cost_exact": len(grouped) == 1,
                "remaining": q,
                "sold_qty": 0,
                "net_revenue": 0.0,
                "tax": 0.0,
            })
        matched_contracts.append((cid, price, grouped, acquired))

    # Exact source-location + type matches for structure/Jita market opportunities.
    for tx in transactions:
        if not bool(tx.get("is_buy")):
            continue
        try:
            tid = int(tx.get("type_id") or 0)
            loc = int(tx.get("location_id") or 0)
            qty = int(tx.get("quantity") or 0)
            unit = float(tx.get("unit_price") or 0)
        except Exception:
            continue
        key = (loc, tid)
        if key not in pushed_markets or qty <= 0:
            continue
        dt = parse_dt(tx.get("date")) or START
        first_sent = pushed_markets[key]["first_sent"]
        if first_sent and dt < first_sent:
            continue
        lots.append({
            "profile": profile,
            "kind": "market",
            "source": "+".join(sorted(pushed_markets[key]["channels"])),
            "opportunity_id": int(tx.get("transaction_id") or 0),
            "type_id": tid,
            "date": dt,
            "quantity": qty,
            "unit_cost": unit,
            "cost_basis": unit * qty,
            "cost_exact": True,
            "remaining": qty,
            "sold_qty": 0,
            "net_revenue": 0.0,
            "tax": 0.0,
        })

    # Allocate later market sales to identified opportunity lots FIFO by type.
    taxes = tax_map(journal)
    by_type = defaultdict(deque)
    for lot in sorted(lots, key=lambda x: x["date"]):
        by_type[lot["type_id"]].append(lot)

    for tx in sorted(transactions, key=lambda x: parse_dt(x.get("date")) or START):
        if bool(tx.get("is_buy")):
            continue
        try:
            tid = int(tx.get("type_id") or 0)
            sell_qty = int(tx.get("quantity") or 0)
            unit = float(tx.get("unit_price") or 0)
            txid = int(tx.get("transaction_id") or 0)
        except Exception:
            continue
        if tid not in by_type or sell_qty <= 0:
            continue
        dt = parse_dt(tx.get("date")) or START
        total_tax = -min(0.0, taxes.get(txid, 0.0))
        left = sell_qty
        q = by_type[tid]
        while left > 0 and q:
            lot = q[0]
            if lot["date"] > dt:
                break
            alloc = min(left, lot["remaining"])
            tax_alloc = total_tax * (alloc / sell_qty)
            lot["remaining"] -= alloc
            lot["sold_qty"] += alloc
            lot["net_revenue"] += unit * alloc - tax_alloc
            lot["tax"] += tax_alloc
            left -= alloc
            if lot["remaining"] <= 0:
                q.popleft()

    for lot in lots:
        realized_cost = lot["unit_cost"] * lot["sold_qty"]
        lot["realized_profit"] = lot["net_revenue"] - realized_cost
        lot["realized_roi"] = (lot["realized_profit"] / realized_cost) if realized_cost > 0 else None
        lot["name"] = type_name(lot["type_id"])
    return lots, matched_contracts


def fmt_isk(v):
    v = float(v or 0)
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1_000_000_000:
        return f"{sign}{a/1_000_000_000:.2f}B"
    if a >= 1_000_000:
        return f"{sign}{a/1_000_000:.1f}M"
    return f"{sign}{a:,.0f}"


def render(profiles_data, pushed_contracts, pushed_markets):
    all_lots = [x for p in profiles_data.values() for x in p["lots"]]
    sold_lots = [x for x in all_lots if x["sold_qty"] > 0]
    total_profit = sum(x["realized_profit"] for x in sold_lots)
    total_realized_cost = sum(x["unit_cost"] * x["sold_qty"] for x in sold_lots)
    total_roi = total_profit / total_realized_cost if total_realized_cost > 0 else 0

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    subject = f"【EVE交易审计】实际捡漏买卖利润 {stamp}"
    plain = [
        f"EVE 三角色实际捡漏交易审计 · {stamp}",
        "",
        f"匹配到捡漏买入批次：{len(all_lots)}",
        f"其中已有卖出的批次：{len(sold_lots)}",
        f"按FIFO归因的已实现净利润：{fmt_isk(total_profit)} ISK",
        f"已实现成本口径ROI：{total_roi*100:.1f}%",
        "",
        "说明：市场机会按“推送过的物品 + 对应来源空间站/建筑 + 后续实际买入”精确匹配；",
        "合同机会按合同ID精确匹配。卖出归因采用FIFO。销售税按可关联到 market_transaction_id 的钱包流水扣除；",
        "无法直接关联的挂单经纪费暂未计入。多物品合同的合同价按当期EVE平均价格分摊，因此该类单品利润为估算；整单总成本仍是实际合同价。",
        "",
    ]

    rows = []
    for profile in PROFILES:
        pd = profiles_data[profile]
        lots = pd["lots"]
        pprofit = sum(x["realized_profit"] for x in lots if x["sold_qty"] > 0)
        plain.append(f"{DISPLAY[profile]}：匹配买入 {len(lots)} 批；已实现利润 {fmt_isk(pprofit)} ISK")
        for x in sorted(lots, key=lambda z: z["date"], reverse=True):
            sold = x["sold_qty"]
            rp = x["realized_profit"]
            tag = "已全部卖出" if sold == x["quantity"] and sold else ("部分卖出" if sold else "尚未匹配到卖出")
            exact = "精确成本" if x["cost_exact"] else "分摊成本"
            plain.append(
                f"  - {x['name']} ×{x['quantity']} | {x['source']} | {tag} | "
                f"买入成本 {fmt_isk(x['cost_basis'])} | 已卖 {sold} | "
                f"已实现利润 {fmt_isk(rp)} | {exact}"
            )
            rows.append(x)
        plain.append("")

    html_rows = []
    for x in sorted(rows, key=lambda z: (z["profile"], z["date"]), reverse=True):
        rp = x["realized_profit"]
        roi = x["realized_roi"]
        html_rows.append(
            "<tr>"
            f"<td>{html.escape(DISPLAY[x['profile']])}</td>"
            f"<td>{html.escape(x['name'])}</td>"
            f"<td>{x['quantity']}</td>"
            f"<td>{html.escape(x['source'])}</td>"
            f"<td>{html.escape(fmt_isk(x['cost_basis']))}</td>"
            f"<td>{x['sold_qty']}</td>"
            f"<td>{html.escape(fmt_isk(x['net_revenue']))}</td>"
            f"<td>{html.escape(fmt_isk(rp))}</td>"
            f"<td>{'' if roi is None else f'{roi*100:.1f}%'}</td>"
            f"<td>{'精确' if x['cost_exact'] else '分摊估算'}</td>"
            "</tr>"
        )

    html_body = f"""<!doctype html><meta charset='utf-8'>
    <div style='font-family:Arial,sans-serif;max-width:1200px;margin:auto'>
      <h2>EVE 三角色实际捡漏交易审计</h2>
      <p>{html.escape(stamp)}</p>
      <div style='padding:12px;background:#f3f4f6;border-radius:8px'>
        <b>已实现净利润：{html.escape(fmt_isk(total_profit))} ISK</b> ·
        已实现成本口径 ROI {total_roi*100:.1f}% · 匹配买入 {len(all_lots)} 批
      </div>
      <p>合同按合同ID精确识别；市场机会按推送物品+来源地点+实际买入匹配。卖出采用FIFO归因，已扣除能按 market_transaction_id 对上的销售税。多物品合同的单品成本为比例分摊。</p>
      <table style='border-collapse:collapse;width:100%;font-size:13px'>
        <tr>
          <th>角色</th><th>物品</th><th>买入数</th><th>机会来源</th><th>买入成本</th>
          <th>已卖</th><th>净回款</th><th>已实现利润</th><th>ROI</th><th>成本口径</th>
        </tr>
        {''.join(html_rows)}
      </table>
    </div>"""
    return subject, "\n".join(plain), html_body


def send_email(subject, plain, html_body):
    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = SMTP_TO
    msg["Subject"] = subject
    msg.set_content(plain)
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)


def main():
    if not (SMTP_USER and SMTP_PASSWORD and API_KEY):
        raise RuntimeError("missing required secrets")

    pushed_contracts, pushed_markets = collect_pushed_opportunities()
    avg_prices = fetch_average_prices()
    profiles_data = {}

    for profile in PROFILES:
        tx = fetch_transactions(profile)
        journal = fetch_paged(profile, "journal", 30)
        contracts_api = fetch_paged(profile, "contracts", 20)
        identity = worker_get(profile, "transactions")
        char_id = int(identity["character_id"])
        lots, matched_contracts = build_lots(
            profile, char_id, tx, journal, contracts_api,
            pushed_contracts, pushed_markets, avg_prices
        )
        profiles_data[profile] = {
            "lots": lots,
            "transactions": len(tx),
            "journal": len(journal),
            "contracts": len(contracts_api),
            "matched_contracts": len(matched_contracts),
        }

    subject, plain, html_body = render(profiles_data, pushed_contracts, pushed_markets)
    send_email(subject, plain, html_body)
    print("private trade audit completed and delivered")


if __name__ == "__main__":
    main()
