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

SOURCE = Path("results/latest/multi_item_grade_watch.csv")
STATE_DIR = Path("results/state")
CHANNEL = "multi-item-grade-watch"
MAIL_TOP = int(os.getenv("MAIL_TOP", "10"))
LIVE_WORKERS = int(os.getenv("LIVE_CHECK_WORKERS", "10"))


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


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
    return STATE_DIR / f"mail_multi_grade_watch_current_{safe_key(name)}.csv"


def current_watch() -> pd.DataFrame:
    df = read_csv(SOURCE)
    if df.empty or "contract_id" not in df.columns:
        return pd.DataFrame()
    grade = df.get("score_grade", pd.Series("", index=df.index)).fillna("").astype(str).str.upper()
    df = df[grade.isin(["A", "S"])].copy()

    # A/S contracts that already qualify for the normal 30M strong-opportunity
    # digest do not need a second duplicate email.
    if "formal_qualified" in df.columns:
        formal = df["formal_qualified"].fillna(False).astype(str).str.lower().isin(["true", "1", "t", "yes"])
        df = df[~formal].copy()

    if df.empty:
        return df
    df["contract_id"] = pd.to_numeric(df["contract_id"], errors="coerce")
    df = df[df["contract_id"].notna()].copy()
    df["contract_id"] = df["contract_id"].astype(int)
    df["opportunity_score"] = pd.to_numeric(df.get("opportunity_score"), errors="coerce").fillna(0.0)
    df["watch_net_profit"] = pd.to_numeric(df.get("watch_net_profit"), errors="coerce").fillna(0.0)
    df["watch_roi"] = pd.to_numeric(df.get("watch_roi"), errors="coerce").fillna(0.0)
    df.sort_values(["opportunity_score", "watch_net_profit", "watch_roi"], ascending=False, inplace=True)
    return df


def load_state(path: Path) -> set[int] | None:
    if not path.exists():
        return None
    df = read_csv(path)
    if df.empty or "contract_id" not in df.columns:
        return set()
    return set(pd.to_numeric(df["contract_id"], errors="coerce").dropna().astype(int).tolist())


def save_state(path: Path, ids: set[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"contract_id": sorted(ids)}).to_csv(path, index=False)


def live_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    rows = df.head(max(MAIL_TOP * 3, MAIL_TOP)).copy()
    states: dict[int, bool] = {}
    with ThreadPoolExecutor(max_workers=min(LIVE_WORKERS, len(rows))) as ex:
        futs = {
            ex.submit(contract_is_live, int(row["contract_id"])): idx
            for idx, row in rows.iterrows()
        }
        for fut in as_completed(futs):
            idx = futs[fut]
            try:
                states[idx] = bool(fut.result())
            except Exception:
                states[idx] = False
    keep = [idx for idx in rows.index if states.get(idx, False)]
    return rows.loc[keep].head(MAIL_TOP).copy()


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


def render(stamp: str, rows: pd.DataFrame) -> tuple[str, str]:
    subject = f"多件捡漏 A/S级新机会提醒 {stamp} · {len(rows)}个"
    parts = [
        f"<b>多件物品捡漏 · A/S级新增提醒</b><br>{stamp}<br><br>",
        "仅提醒本轮新进入 A/S 级集合的合同；上线前已有的存量 A/S 不补发，持续留在 A/S 也不重复提醒。<br>",
        "这是注意提醒，不改变正式强机会门槛：正式频道仍要求净利润≥3000万 ISK、ROI≥10%。<br><br>",
    ]
    for i, (_, r) in enumerate(rows.iterrows(), 1):
        cid = int(r["contract_id"])
        grade = html.escape(str(r.get("score_grade", "")))
        score = float(r.get("opportunity_score", 0) or 0)
        status = html.escape(str(r.get("execution_status", "")))
        klass = html.escape(str(r.get("watch_class", "")))
        risk = html.escape(str(r.get("risk_tier", "")))
        system = html.escape(str(r.get("system_name", "")))
        station = html.escape(str(r.get("station_name", "")))
        profit = float(r.get("watch_net_profit", 0) or 0)
        roi = float(r.get("watch_roi", 0) or 0)
        stress = float(r.get("stress_net_profit", 0) or 0)
        coverage = float(r.get("buy_unit_coverage", 0) or 0) * 100
        items = html.escape(" ".join(str(r.get("top_value_items", "") or "").split())[:420])
        parts.append(
            f"<b>{i}. {grade}级 · 评分 {score:.1f} · {status} · {klass}</b><br>"
            f"合同价 {fmt_isk(r.get('contract_price',0))} · 预估净利润 <b>{fmt_isk(profit)}</b> · ROI {roi*100:.1f}%<br>"
            f"压力利润 {fmt_isk(stress)} · 当前买单覆盖 {coverage:.1f}% · {risk}<br>"
            f"位置 {system} / {station}<br>"
            + (f"主要价值：{items}<br>" if items else "")
            + f"<url=contract:0//{cid}><b>打开合同</b></url><br><br>"
        )
    return subject, "".join(parts)


def main() -> None:
    if not base.API_KEY:
        raise RuntimeError("Missing EVE_MAIL_API_KEY")

    current = current_watch()
    current_ids = set(current["contract_id"].astype(int).tolist()) if not current.empty else set()
    names = recipient_names()
    primary = os.getenv("EVE_MAIL_RECIPIENT_NAME", "").strip() or names[0]
    failures = []

    for name in names:
        path = state_path(name)
        previous = load_state(path)

        # First production run is baseline-only by design: existing A/S stock is
        # remembered but never mailed.
        if previous is None:
            save_state(path, current_ids)
            print(f"{CHANNEL} baseline initialized for {name}: current={len(current_ids)}; no stock mail")
            continue

        new_ids = current_ids - previous
        if not new_ids:
            save_state(path, current_ids)
            print(f"{CHANNEL} skipped for {name}: no newly-entered A/S contracts")
            continue

        new_df = current[current["contract_id"].isin(new_ids)].copy()
        picked = live_rows(new_df)
        if picked.empty:
            # Do not mark unseen candidates as delivered; if they remain A/S and
            # become live/visible next round they can still trigger.
            save_state(path, current_ids - new_ids)
            print(f"{CHANNEL} no live new A/S contracts for {name}; pending={len(new_ids)}")
            continue

        stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")
        subject, body = render(stamp, picked)
        recipient_id = resolve_character(name)
        try:
            send_with_retry(recipient_id, subject, body, name)
            sent_ids = set(picked["contract_id"].astype(int).tolist())
            # Persist current old members plus only the newly delivered IDs.
            # Extra new IDs beyond MAIL_TOP stay unseen and can alert next round.
            save_state(path, (current_ids & previous) | sent_ids)
            print(f"{CHANNEL} sent to {name}: new={len(sent_ids)} pending={len(new_ids - sent_ids)}")
        except Exception as exc:
            failures.append((name, exc))
            print(f"::warning::{CHANNEL} failed for {name}: {type(exc).__name__}: {exc}")

    if failures:
        primary_failures = [exc for name, exc in failures if name.casefold() == primary.casefold()]
        if primary_failures:
            raise RuntimeError(f"{CHANNEL} delivery failed for primary recipient")


if __name__ == "__main__":
    main()
