from __future__ import annotations

import html
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

import send_eve_mail_dual as base
from send_eve_mail_fast import contract_is_live, fmt_isk, resolve_character

STATE_DIR = Path("results/state")
LATEST = Path("results/latest")
CHANNEL = "global-grade-watch"
MAIL_TOP = int(os.getenv("GRADE_WATCH_MAIL_TOP", "10"))
LIVE_WORKERS = int(os.getenv("LIVE_CHECK_WORKERS", "10"))
MIN_SCORE = float(os.getenv("GRADE_WATCH_MIN_SCORE", "70"))
BPC_MFG_MAIL_EXCLUDED_RECIPIENTS = {
    x.strip().casefold()
    for x in os.getenv("BPC_MFG_MAIL_EXCLUDED_RECIPIENTS", "").split(",")
    if x.strip()
}

SOURCES = [
    {
        "path": "contract_deals_all.csv",
        "label": "普通合同V2",
        "identity": "contract",
        "score": ["opportunity_score", "deal_score"],
        "grade": ["score_grade"],
        "status": ["execution_status"],
    },
    {
        "path": "multi_item_grade_watch.csv",
        "label": "多件合同",
        "identity": "contract",
        "score": ["opportunity_score"],
        "grade": ["score_grade"],
        "status": ["execution_status"],
    },
    {
        "path": "ranked_opportunities_v2.csv",
        "label": "BPC制造",
        "identity": "contract",
        "score": ["v2_score", "opportunity_score"],
        "grade": ["v2_grade"],
        "status": ["v2_status"],
    },
    {
        "path": "bpc_value_opportunities_v2.csv",
        "label": "BPC价值低估",
        "identity": "contract",
        "score": ["v2_value_score", "bpc_value_score"],
        "grade": [],
        "status": ["v2_value_status"],
    },
    {
        "path": "four_h_contract_bargains.csv",
        "label": "4-H合同",
        "identity": "contract",
        "score": ["opportunity_score"],
        "grade": ["score_grade"],
        "status": ["execution_status"],
    },
    {
        "path": "four_h_to_jita_buy.csv",
        "label": "4-H→吉他市场",
        "identity": "market:4h-to-jita",
        "score": ["opportunity_score"],
        "grade": ["score_grade"],
        "status": ["execution_status"],
    },
    {
        "path": "v3_cash_floor.csv",
        "label": "V3现金底价",
        "identity": "contract",
        "score": ["opportunity_score"],
        "grade": ["score_grade"],
        "status": ["execution_status"],
    },
    {
        "path": "v3_barter.csv",
        "label": "V3以物易物",
        "identity": "contract",
        "score": ["opportunity_score"],
        "grade": ["score_grade"],
        "status": ["execution_status"],
    },
    {
        "path": "v3_conservative_listing.csv",
        "label": "V3保守挂卖",
        "identity": "contract",
        "score": ["opportunity_score"],
        "grade": ["score_grade"],
        "status": ["execution_status"],
    },
    {
        "path": "v3_jita_to_four_h.csv",
        "label": "吉他→4-H市场",
        "identity": "market:jita-to-4h",
        "score": ["opportunity_score"],
        "grade": ["score_grade"],
        "status": ["execution_status"],
    },
]


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (pd.errors.EmptyDataError, UnicodeDecodeError):
        return pd.DataFrame()


def finite(v, default=0.0) -> float:
    try:
        x = float(v)
        if pd.isna(x) or x in (float("inf"), float("-inf")):
            return default
        return x
    except Exception:
        return default


def text_value(v, default="") -> str:
    if v is None:
        return default
    s = str(v).strip()
    if not s or s.lower() in {"nan", "none"}:
        return default
    return s


def first_value(row, names, default=None):
    for name in names:
        if name in row.index:
            value = row.get(name)
            if value is not None and not (isinstance(value, float) and pd.isna(value)):
                return value
    return default


def grade_from_score(score: float) -> str:
    if score >= 85:
        return "S"
    if score >= 70:
        return "A"
    if score >= 55:
        return "B"
    if score >= 40:
        return "C"
    return "D"


def recipient_names() -> list[str]:
    raw = os.getenv("EVE_MAIL_RECIPIENT_NAMES", "").strip()
    if raw:
        names = [x.strip() for x in raw.split(",") if x.strip()]
    else:
        names = [os.getenv("EVE_MAIL_RECIPIENT_NAME", "MikeChong").strip()]
    return list(dict.fromkeys(names))


def safe_key(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())
    return s.strip("_") or "recipient"


def state_path(name: str) -> Path:
    return STATE_DIR / f"mail_global_grade_watch_seen_{safe_key(name)}.csv"


def load_seen(path: Path) -> set[str] | None:
    if not path.exists():
        return None
    df = read_csv(path)
    if df.empty or "opportunity_key" not in df.columns:
        return set()
    return set(df["opportunity_key"].dropna().astype(str).tolist())


def save_seen(path: Path, seen: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    now = pd.Timestamp.now(tz="UTC").isoformat()
    pd.DataFrame(
        [{"opportunity_key": k, "recorded_at": now} for k in sorted(seen)],
        columns=["opportunity_key", "recorded_at"],
    ).to_csv(path, index=False)


def entity_identity(spec, row) -> tuple[str, int | None, int | None] | None:
    mode = spec["identity"]
    if mode == "contract":
        cid = int(finite(row.get("contract_id"), 0))
        if cid <= 0:
            return None
        return f"contract:{cid}", cid, None
    tid = int(finite(row.get("type_id"), 0))
    if tid <= 0:
        return None
    return f"{mode}:{tid}", None, tid


def candidate_title(spec, row) -> str:
    for field in (
        "item_name",
        "contract_title",
        "title",
        "blueprints",
        "products",
        "items",
        "blueprint_name",
    ):
        value = text_value(row.get(field))
        if value:
            return value
    return spec["label"]


def candidate_profit(row) -> float:
    return finite(first_value(row, [
        "net_profit",
        "best_net_profit",
        "watch_net_profit",
        "v2_live_net_profit",
        "instant_net_profit",
        "chosen_value_gap",
        "bpc_intrinsic_value_surplus",
    ], 0.0), 0.0)


def candidate_roi(row) -> float | None:
    value = first_value(row, [
        "net_roi",
        "best_roi",
        "watch_roi",
        "v2_live_net_roi",
        "instant_net_roi",
        "chosen_roi",
    ], None)
    if value is None:
        return None
    return finite(value, 0.0)


def candidate_stress(row) -> float | None:
    value = first_value(row, [
        "stress_net_profit",
        "v2_stress_net_profit",
    ], None)
    if value is None:
        return None
    return finite(value, 0.0)


def candidate_location(row) -> tuple[str, str]:
    system = text_value(first_value(row, ["system_name", "factory_system"], ""))
    station = text_value(first_value(row, ["station_name", "factory_station"], ""))
    return system, station


def candidate_note(spec, row) -> str:
    if spec["label"] == "BPC价值低估":
        return "这是同类BPC挂牌估值信号，不等于即时可兑现利润。"
    if spec["label"] == "V3保守挂卖":
        return "这是保守挂卖估值，包含成交时间与流动性假设。"
    if spec["label"] == "多件合同" and text_value(row.get("watch_class")) == "现金底价":
        return "现金底价只计算当前可立即兑现部分，未成交剩余按0估值。"
    return ""


def collect_candidates() -> tuple[dict[str, dict], int]:
    best: dict[str, dict] = {}
    readable_sources = 0

    for spec in SOURCES:
        path = LATEST / spec["path"]
        if path.exists():
            readable_sources += 1
        df = read_csv(path)
        if df.empty:
            continue

        for _, row in df.iterrows():
            score = finite(first_value(row, spec["score"], 0.0), 0.0)
            grade = text_value(first_value(row, spec["grade"], "")).upper() if spec["grade"] else grade_from_score(score)
            if score < MIN_SCORE and grade not in {"A", "S"}:
                continue

            status = text_value(first_value(row, spec["status"], ""), "").upper()
            if status == "DANGER":
                continue
            if spec["label"] == "BPC价值低估":
                live_flag = text_value(row.get("v2_contract_live"), "true").lower()
                if live_flag in {"false", "0", "no"}:
                    continue

            ident = entity_identity(spec, row)
            if ident is None:
                continue
            key, contract_id, type_id = ident
            system, station = candidate_location(row)

            record = {
                "opportunity_key": key,
                "contract_id": contract_id,
                "type_id": type_id,
                "score": score,
                "grade": grade_from_score(score) if grade not in {"A", "S"} else grade,
                "status": status or "WATCH",
                "source_labels": [spec["label"]],
                "primary_source": spec["label"],
                "title": candidate_title(spec, row),
                "profit": candidate_profit(row),
                "roi": candidate_roi(row),
                "stress_profit": candidate_stress(row),
                "system_name": system,
                "station_name": station,
                "risk_tier": text_value(row.get("risk_tier")),
                "items": text_value(first_value(row, ["top_value_items", "cash_items", "top_items", "items", "products"], "")),
                "note": candidate_note(spec, row),
                "eve_contract_url": text_value(row.get("eve_contract_url")),
                "eve_market_url": text_value(row.get("eve_market_url")),
            }

            old = best.get(key)
            if old is None:
                best[key] = record
            else:
                labels = list(dict.fromkeys(old["source_labels"] + [spec["label"]]))
                if score > old["score"]:
                    record["source_labels"] = labels
                    best[key] = record
                else:
                    old["source_labels"] = labels

    return best, readable_sources


def live_filter(records: list[dict]) -> list[dict]:
    contract_rows = [r for r in records if r["contract_id"]]
    market_rows = [r for r in records if not r["contract_id"]]
    if not contract_rows:
        return market_rows

    states: dict[int, bool] = {}
    with ThreadPoolExecutor(max_workers=min(LIVE_WORKERS, len(contract_rows))) as ex:
        futs = {
            ex.submit(contract_is_live, int(r["contract_id"])): int(r["contract_id"])
            for r in contract_rows
        }
        for fut in as_completed(futs):
            cid = futs[fut]
            try:
                states[cid] = bool(fut.result())
            except Exception:
                states[cid] = False

    return [r for r in contract_rows if states.get(int(r["contract_id"]), False)] + market_rows


def send_with_retry(recipient_id: int, subject: str, body: str, name: str) -> None:
    for attempt in range(1, 4):
        try:
            print(f"sending {CHANNEL} to {name} ({recipient_id}) attempt={attempt}")
            base.send_mail(recipient_id, subject, body, CHANNEL)
            return
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            if status < 500 or attempt >= 3:
                raise
            delay = 2 * attempt
            print(f"{CHANNEL} upstream HTTP {status}; retry {name} in {delay}s")
            time.sleep(delay)


def render(stamp: str, rows: list[dict], batch_no: int, batch_total: int) -> tuple[str, str]:
    suffix = f" {batch_no}/{batch_total}" if batch_total > 1 else ""
    subject = f"全局 A/S级新机会提醒 {stamp} · {len(rows)}个{suffix}"
    parts = [
        f"<b>全局捡漏 · A/S级首次出现提醒</b><br>{stamp}<br><br>",
        "覆盖普通合同、多件合同、BPC制造/BPC价值、4-H合同与市场、V3现金底价/以物易物/保守挂卖、吉他→4-H。<br>",
        "上线前已有A/S机会仅记为基线，不补发；同一机会一旦记录为已见，以后不因排名或再次升回A/S而重复发送。<br>",
        "这是高评分注意提醒，不改变各正式频道原有利润、ROI和安全门槛。<br><br>",
    ]

    for i, r in enumerate(rows, 1):
        labels = " + ".join(r["source_labels"])
        title = html.escape(r["title"][:180])
        system = html.escape(r["system_name"][:50])
        station = html.escape(r["station_name"][:90])
        risk = html.escape(r["risk_tier"][:40])
        items = html.escape(r["items"][:380])
        note = html.escape(r["note"][:180])
        roi = r["roi"]
        stress = r["stress_profit"]

        parts.append(
            f"<b>{i}. {r['grade']}级 · {r['score']:.1f}分 · {html.escape(r['status'])}</b><br>"
            f"来源：{html.escape(labels)}<br>"
            f"{title}<br>"
        )

        if r["primary_source"] == "BPC价值低估":
            parts.append(f"估值价差 {fmt_isk(r['profit'])}")
        else:
            parts.append(f"净利润/价值差 {fmt_isk(r['profit'])}")
        if roi is not None:
            parts.append(f" · ROI {roi*100:.1f}%")
        parts.append("<br>")

        if stress is not None:
            parts.append(f"压力情景利润 {fmt_isk(stress)}<br>")
        if system or station:
            parts.append(f"位置 {system} / {station}")
            if risk:
                parts.append(f" · {risk}")
            parts.append("<br>")
        if items:
            parts.append(f"主要价值：{items}<br>")
        if note:
            parts.append(f"{note}<br>")

        if r["contract_id"]:
            cid = int(r["contract_id"])
            parts.append(f"<url=contract:0//{cid}><b>打开合同</b></url><br><br>")
        elif r["eve_market_url"]:
            parts.append(f"<url={html.escape(r['eve_market_url'])}><b>查看市场</b></url><br><br>")
        else:
            parts.append("<br>")

    return subject, "".join(parts)


def main() -> None:
    if not base.API_KEY:
        raise RuntimeError("Missing EVE_MAIL_API_KEY")

    candidates, readable_sources = collect_candidates()
    if readable_sources < 6:
        raise RuntimeError(f"Grade watch source set incomplete: readable_sources={readable_sources}")

    current_keys = set(candidates)
    print(f"{CHANNEL}: current A/S identities={len(current_keys)} readable_sources={readable_sources}")

    names = recipient_names()
    primary = os.getenv("EVE_MAIL_RECIPIENT_NAME", "").strip() or names[0]
    failures = []

    for name in names:
        path = state_path(name)
        seen = load_seen(path)

        # First production run is baseline-only. This is the explicit no-stock-mail
        # rule requested by the user.
        if seen is None:
            save_seen(path, current_keys)
            print(f"{CHANNEL} baseline initialized for {name}: {len(current_keys)} existing A/S identities; no stock mail")
            continue

        new_keys = current_keys - seen
        excluded_keys = {
            k
            for k in new_keys
            if name.casefold() in BPC_MFG_MAIL_EXCLUDED_RECIPIENTS
            and candidates[k].get("primary_source") == "BPC制造"
        }
        if excluded_keys:
            seen = seen | excluded_keys
            save_seen(path, seen)
            print(
                f"{CHANNEL} suppressed for {name}: "
                f"BPC manufacturing first_seen={len(excluded_keys)}"
            )

        eligible_keys = new_keys - excluded_keys
        if not eligible_keys:
            print(f"{CHANNEL} skipped for {name}: no first-seen A/S opportunity after recipient filters")
            continue

        ordered = sorted(
            (candidates[k] for k in eligible_keys),
            key=lambda r: (r["score"], r["profit"], r["roi"] or 0.0),
            reverse=True,
        )
        live = live_filter(ordered)
        if not live:
            print(f"{CHANNEL}: new high-score identities were not live/visible; no mail for {name}")
            continue

        # Send every first-seen high-score opportunity, batching to keep EVE mail bodies
        # compact. Only successfully delivered keys are persisted as seen.
        batches = [live[i:i + MAIL_TOP] for i in range(0, len(live), MAIL_TOP)]
        recipient_id = resolve_character(name)
        sent_keys: set[str] = set()
        try:
            for batch_no, batch in enumerate(batches, 1):
                stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")
                subject, body = render(stamp, batch, batch_no, len(batches))
                send_with_retry(recipient_id, subject, body, name)
                sent_keys.update(r["opportunity_key"] for r in batch)
            save_seen(path, seen | sent_keys)
            print(f"{CHANNEL} sent to {name}: first_seen={len(sent_keys)}")
        except Exception as exc:
            failures.append((name, exc))
            # Preserve successfully sent batches in state so a later retry does not
            # duplicate them.
            if sent_keys:
                save_seen(path, seen | sent_keys)
            print(f"::warning::{CHANNEL} failed for {name}: {type(exc).__name__}: {exc}")

    if failures:
        primary_failures = [exc for name, exc in failures if name.casefold() == primary.casefold()]
        if primary_failures:
            raise RuntimeError(f"{CHANNEL} delivery failed for primary recipient")


if __name__ == "__main__":
    main()
