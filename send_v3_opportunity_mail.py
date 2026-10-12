from __future__ import annotations

import html
import os
import re
import time
from pathlib import Path

import pandas as pd
import requests

from mail_profit_policy import MAIL_MIN_VERIFIED_NET_PROFIT
from send_eve_mail_dual import send_mail
from send_eve_mail_fast import contract_is_live, fmt_isk, resolve_character
from v3_scan_health import channel_healthy

LATEST = Path("results/latest")
STATE = Path("results/state")
MAIL_TOP = int(os.getenv("MAIL_TOP", "10"))
POLICY_VERSION = "opportunity-v3-production-2026-10-07-r2"
RESEND_ABS_PROFIT = float(os.getenv("MAIL_RESEND_ABS_PROFIT", "20000000"))
RESEND_REL_PROFIT = float(os.getenv("MAIL_RESEND_REL_PROFIT", "0.10"))
RESEND_ROI_DELTA = float(os.getenv("MAIL_RESEND_ROI_DELTA", "0.02"))
REMIND_AFTER_HOURS = float(os.getenv("MAIL_REMIND_AFTER_HOURS", "6"))

CHANNELS = {
    "v3-full-cash": {
        "path": LATEST / "v3_full_cash.csv",
        "id_col": "contract_id",
        "title": "现金合同",
        "kind": "contract",
    },
    "v3-cash-floor": {
        "path": LATEST / "v3_cash_floor.csv",
        "id_col": "contract_id",
        "title": "现金底价",
        "kind": "contract",
    },
    "v3-barter": {
        "path": LATEST / "v3_barter.csv",
        "id_col": "contract_id",
        "title": "以物换物",
        "kind": "contract",
    },
    "v3-conservative-list": {
        "path": LATEST / "v3_conservative_listing.csv",
        "id_col": "contract_id",
        "title": "挂卖观察",
        "kind": "contract",
    },
    "v3-four-h-contract": {
        "path": LATEST / "v3_four_h_contracts.csv",
        "id_col": "contract_id",
        "title": "4-H合同",
        "kind": "structure-contract",
    },
    "v3-cj-contract": {
        "path": LATEST / "v3_cj_contracts.csv",
        "id_col": "contract_id",
        "title": "C-J合同",
        "kind": "structure-contract",
    },
    "v3-amarr-to-jita": {
        "path": LATEST / "v3_amarr_to_jita.csv",
        "id_col": "type_id",
        "title": "Amarr→Jita",
        "kind": "source-market",
    },
    "v3-dodixie-to-jita": {
        "path": LATEST / "v3_dodixie_to_jita.csv",
        "id_col": "type_id",
        "title": "Dodixie→Jita",
        "kind": "source-market",
    },
    "v3-four-h-to-jita": {
        "path": LATEST / "v3_four_h_to_jita.csv",
        "id_col": "type_id",
        "title": "4-H→Jita",
        "kind": "source-market",
    },
    "v3-cj-to-jita": {
        "path": LATEST / "v3_cj_to_jita.csv",
        "id_col": "type_id",
        "title": "C-J→Jita",
        "kind": "source-market",
    },
    "v3-dc-o4t-contract": {
        "path": LATEST / "v3_dc_o4t_contracts.csv",
        "id_col": "contract_id",
        "title": "O4T Prime合同",
        "kind": "structure-contract",
    },
    "v3-dc-o4t-to-jita": {
        "path": LATEST / "v3_dc_o4t_to_jita.csv",
        "id_col": "type_id",
        "title": "O4T Prime→Jita",
        "kind": "source-market",
    },
    "v3-jita-to-4h": {
        "path": LATEST / "v3_jita_to_four_h.csv",
        "id_col": "type_id",
        "title": "Jita→4-H",
        "kind": "reverse-market",
    },
    "v3-bpc": {
        "path": LATEST / "v3_bpc_opportunities.csv",
        "id_col": "contract_id",
        "title": "BPC制造",
        "kind": "bpc",
    },
}


def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _num(v, default=0.0):
    try:
        x = float(v)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _text(v, default=""):
    if v is None:
        return default
    s = str(v).strip()
    if not s or s.lower() in {"nan", "none"}:
        return default
    return s


def recipient_names():
    raw = os.getenv("EVE_MAIL_RECIPIENT_NAMES", "").strip()
    if raw:
        names = [x.strip() for x in raw.split(",") if x.strip()]
    else:
        names = [os.getenv("EVE_MAIL_RECIPIENT_NAME", "MikeChong").strip() or "MikeChong"]
    return list(dict.fromkeys(names))


def enabled_channels():
    raw = os.getenv("V3_CHANNELS", "").strip()
    if not raw:
        return list(CHANNELS)
    wanted = [x.strip() for x in raw.split(",") if x.strip()]
    unknown = [x for x in wanted if x not in CHANNELS]
    if unknown:
        raise RuntimeError(f"Unknown V3 channel(s): {','.join(unknown)}")
    return wanted


def safe_key(name: str):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "recipient"


def state_path(channel: str, recipient: str):
    return STATE / f"mail_last_{channel}_{safe_key(recipient)}.csv"


def build_candidates(channel: str):
    cfg = CHANNELS[channel]
    df = _read(cfg["path"])
    if df.empty or cfg["id_col"] not in df.columns:
        return []

    if "mail_eligible" in df.columns:
        df = df[df["mail_eligible"].fillna(False).astype(str).str.lower().isin({"1", "true", "t", "yes", "y"})].copy()
    elif "execution_status" in df.columns:
        df = df[df["execution_status"].fillna("").astype(str).str.upper().eq("SAFE")].copy()
    if df.empty:
        return []

    profit = pd.to_numeric(df.get("net_profit"), errors="coerce").fillna(0.0)
    roi = pd.to_numeric(df.get("net_roi"), errors="coerce").fillna(0.0)
    score = pd.to_numeric(df.get("opportunity_score"), errors="coerce").fillna(0.0)
    df = df.assign(_profit=profit, _roi=roi, _score=score)
    df = df[(df["_profit"] >= MAIL_MIN_VERIFIED_NET_PROFIT) & (df["_roi"] > 0)].copy()
    df.sort_values(["_score", "_profit", "_roi"], ascending=False, inplace=True)

    out = []
    needs_live_contract = cfg["kind"] in {"contract", "structure-contract", "bpc"}
    candidate_limit = MAIL_TOP * 3 if needs_live_contract else MAIL_TOP
    for _, r in df.head(candidate_limit).iterrows():
        try:
            ident = int(float(r[cfg["id_col"]]))
        except Exception:
            continue

        if needs_live_contract:
            try:
                if not contract_is_live(ident):
                    print(f"{channel}: skip stale contract {ident}")
                    continue
            except Exception as exc:
                print(f"{channel}: live check failed closed for {ident}: {type(exc).__name__}: {exc}")
                continue

        out.append(
            {
                "id": ident,
                "profit": float(r["_profit"]),
                "roi": float(r["_roi"]),
                "score": float(r["_score"]),
                "grade": _text(r.get("score_grade")),
                "row": r,
            }
        )
        if len(out) >= MAIL_TOP:
            break
    return out


def seen_path(channel: str, recipient: str) -> Path:
    """Append-only per-recipient, per-channel identity ledger (never TOP-only)."""
    return STATE / f"mail_seen_{channel}_{safe_key(recipient)}.csv"


def _read_seen_ids(path: Path) -> set[int]:
    df = _read(path)
    if df.empty or "id" not in df.columns:
        return set()
    return {int(x) for x in pd.to_numeric(df["id"], errors="coerce").dropna() if int(x) > 0}


def _write_seen_ids(path: Path, ids: set[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    pd.DataFrame({"id": sorted(ids)}).to_csv(tmp, index=False)
    tmp.replace(path)


def pending_candidates(channel: str, recipient: str, picked):
    """Return ONLY not-yet-mailed opportunities. No repeat for a known ID.

    Until we can prove a genuinely new order_id/book fingerprint, a type_id
    price/ROI change is not proof of a new trade. Contract IDs are immutable.
    """
    path = seen_path(channel, recipient)
    if not path.exists():
        legacy = state_path(channel, recipient)
        baseline = _read_seen_ids(legacy)
        if legacy.exists():
            # Migration from legacy TOP snapshot: do not re-send its old IDs
            # or backfill the currently visible list as "new" on rollout.
            baseline |= {int(c["id"]) for c in picked}
            print(f"{channel} {recipient}: initialized historical sent baseline ({len(baseline)} ids); no backfill")
        _write_seen_ids(path, baseline)
    seen = _read_seen_ids(path)
    return [c for c in picked if int(c["id"]) not in seen]


def acknowledge_seen(channel: str, recipient: str, delivered) -> None:
    """Advance the lifetime ledger only AFTER successful delivery."""
    path = seen_path(channel, recipient)
    old = _read_seen_ids(path)
    old.update(int(c["id"]) for c in delivered)
    _write_seen_ids(path, old)


def should_suppress(channel: str, recipient: str, picked):
    """Compatibility helper; the sender must send only pending IDs."""
    return not pending_candidates(channel, recipient, picked)


def save_state(channel: str, recipient: str, picked):
    path = state_path(channel, recipient)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = pd.Timestamp.now(tz="UTC").isoformat()
    rows = []
    for rank, c in enumerate(picked, 1):
        rows.append(
            {
                "policy_version": POLICY_VERSION,
                "rank": rank,
                "id": c["id"],
                "profit": c["profit"],
                "roi": c["roi"],
                "grade": c["grade"],
                "sent_at": now,
            }
        )
    pd.DataFrame(rows, columns=["policy_version", "rank", "id", "profit", "roi", "grade", "sent_at"]).to_csv(path, index=False)


def _loc(r):
    system = html.escape(_text(r.get("system_name"), "未知"))
    station = html.escape(_text(r.get("station_name"), ""))
    jumps = int(_num(r.get("shortest_jumps_to_jita"), -1))
    risk = html.escape(_text(r.get("risk_tier"), ""))
    bits = [system]
    if station:
        bits.append(station)
    if jumps >= 0:
        bits.append(f"Jita {jumps}跳")
    if risk:
        bits.append(risk)
    return " · ".join(bits)


def _render_public_contract(i, c, r):
    items = html.escape(_text(r.get("cash_items", r.get("items", ""))))
    where = _loc(r)
    cost = fmt_isk(r.get("contract_price", r.get("source_cost", 0)))
    return (
        f"<b>{i}. 合同 {c['id']}</b><br>"
        f"净利 <b>{fmt_isk(c['profit'])}</b>｜ROI {c['roi']:.1%}｜压力 {fmt_isk(r.get('stress_net_profit',0))}<br>"
        f"成本 {cost}" + (f"｜{where}" if where else "") + "<br>"
        + (f"{items}<br>" if items else "")
        + f"<url=contract:0//{c['id']}><b>打开合同</b></url><br><br>"
    )


def _render_structure_contract(i, c, r):
    source = html.escape(_text(r.get("source_label"), "-"))
    exit_market = html.escape(_text(r.get("exit_market"), "Jita买单"))
    items = html.escape(_text(r.get("items"), ""))
    return (
        f"<b>{i}. 合同 {c['id']}</b><br>"
        f"净利 <b>{fmt_isk(c['profit'])}</b>｜ROI {c['roi']:.1%}｜压力 {fmt_isk(r.get('stress_net_profit',0))}<br>"
        f"{source}｜成本 {fmt_isk(r.get('contract_price', r.get('source_cost',0)))}｜退出 {exit_market}<br>"
        + (f"{items}<br>" if items else "")
        + f"<url=contract:0//{c['id']}><b>打开合同</b></url><br><br>"
    )


def _render_source_market(i, c, r):
    tid = int(c["id"])
    source = html.escape(_text(r.get("source_label"), "-"))
    item = html.escape(_text(r.get("item_name"), str(tid)))
    qty = int(_num(r.get("quantity")))
    return (
        f"<b>{i}. {item} ×{qty:,}</b><br>"
        f"净利 <b>{fmt_isk(c['profit'])}</b>｜ROI {c['roi']:.1%}｜压力 {fmt_isk(r.get('stress_net_profit',0))}<br>"
        f"{source} {fmt_isk(r.get('source_best_sell',0))}/件 → Jita买单 {fmt_isk(r.get('jita_best_buy',0))}/件<br>"
        f"<url=showinfo:{tid}><b>查看物品</b></url><br><br>"
    )


def _render_reverse_market(i, c, r):
    tid = int(c["id"])
    item = html.escape(_text(r.get("item_name"), str(tid)))
    qty = int(_num(r.get("quantity")))
    return (
        f"<b>{i}. {item} ×{qty:,}</b><br>"
        f"净利 <b>{fmt_isk(c['profit'])}</b>｜ROI {c['roi']:.1%}｜压力 {fmt_isk(r.get('stress_net_profit',0))}<br>"
        f"Jita {fmt_isk(r.get('jita_best_sell',0))}/件 → 4-H买单 {fmt_isk(r.get('four_h_best_buy',0))}/件<br>"
        f"<url=showinfo:{tid}><b>查看物品</b></url><br><br>"
    )


def _render_bpc(i, c, r):
    products = html.escape(_text(r.get("products"), "BPC制造机会"))
    blueprints = html.escape(_text(r.get("blueprints"), ""))
    return (
        f"<b>{i}. {products}</b><br>"
        f"合同 {c['id']}｜成本 {fmt_isk(r.get('contract_price',0))}<br>"
        f"Jita制造净利 <b>{fmt_isk(c['profit'])}</b>｜ROI {c['roi']:.1%}｜压力 {fmt_isk(r.get('stress_net_profit',0))}<br>"
        + (f"{blueprints}<br>" if blueprints else "")
        + f"<url=contract:0//{c['id']}><b>打开合同</b></url><br><br>"
    )


def render(channel: str, stamp: str, picked):
    cfg = CHANNELS[channel]
    count = len(picked)
    subject = f"[V3] {cfg['title']} · {count}个 · {stamp}"
    if not picked:
        return subject, f"<b>{cfg['title']}｜暂无机会</b><br>{stamp}"

    parts = [f"<b>{cfg['title']}｜{count}个</b><br>{stamp}<br><br>"]
    for i, c in enumerate(picked, 1):
        r = c["row"]
        kind = cfg["kind"]
        if channel == "v3-barter":
            parts.append(
                f"<b>{i}. 合同 {c['id']}</b><br>"
                f"净利 <b>{fmt_isk(c['profit'])}</b>｜ROI {c['roi']:.1%}｜压力 {fmt_isk(r.get('stress_net_profit',0))}<br>"
                f"需提供：{html.escape(_text(r.get('provide_items')))}<br>"
                f"可收到：{html.escape(_text(r.get('receive_items')))}<br>"
                f"<url=contract:0//{c['id']}><b>打开合同</b></url><br><br>"
            )
        elif channel == "v3-conservative-list":
            parts.append(
                f"<b>{i}. 合同 {c['id']}</b><br>"
                f"净利估算 <b>{fmt_isk(c['profit'])}</b>｜ROI {c['roi']:.1%}｜压力 {fmt_isk(r.get('stress_net_profit',0))}<br>"
                f"预计消化 {_num(r.get('estimated_fill_days')):.1f}天<br>"
                f"<url=contract:0//{c['id']}><b>打开合同</b></url><br><br>"
            )
        elif kind == "structure-contract":
            parts.append(_render_structure_contract(i, c, r))
        elif kind == "source-market":
            parts.append(_render_source_market(i, c, r))
        elif kind == "reverse-market":
            parts.append(_render_reverse_market(i, c, r))
        elif kind == "bpc":
            parts.append(_render_bpc(i, c, r))
        else:
            parts.append(_render_public_contract(i, c, r))
    return subject, "".join(parts)


def send_with_retry(recipient_id, subject, body, channel, name):
    """Do not hammer the ESI monolith after a 520 rate-limit response."""
    for attempt in range(1, 3):
        try:
            print(f"sending consolidated {channel} to {name} ({recipient_id}) attempt={attempt}")
            return send_mail(recipient_id, subject, body, channel)
        except requests.exceptions.HTTPError as exc:
            detail = exc.response.text if exc.response is not None else ""
            status = exc.response.status_code if exc.response is not None else 0
            if "EVE mail failed (520)" in detail:
                print(f"::warning::EVE mail ESI 520 monolith rate limit: {name}; stop retries for this scan and preserve state")
                raise
            if status not in (502, 503, 504) or attempt >= 2:
                raise
            time.sleep(5 * attempt)


MAIL_DIGEST_BODY_LIMIT = 6800


def compose_digest(entries, stamp, *, max_body_chars=MAIL_DIGEST_BODY_LIMIT):
    """At most one mail per recipient per scan, never an empty-opportunity mail.

    Return only channels actually included. Other changed channels keep their
    old sent-state and will be eligible in the following scan.
    """
    header = f"<b>V3正式捡漏机会汇总</b><br>{stamp}<br><br>"
    body = header
    included = []
    for channel, picked in entries:
        if not picked:
            continue
        displayed = list(picked)
        _, section = render(channel, stamp, displayed)
        while len(body) + len(section) > max_body_chars and len(displayed) > 1:
            displayed.pop()
            _, section = render(channel, stamp, displayed)
        if len(displayed) < len(picked):
            section += f"<br>本频道共{len(picked)}条，只显示前{len(displayed)}条；完整数据请查看扫描结果。<br>"
        if len(body) + len(section) > max_body_chars:
            print(f"::warning::{channel}: deferred from bundled game mail due to body limit")
            continue
        body += section + "<br>"
        # Only acknowledge what was actually rendered, not omitted TOP rows.\n        included.append((channel, displayed))
    return included, body


def main():
    names = recipient_names()
    recipients = [(name, resolve_character(name)) for name in names]
    stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")
    failures = []
    eligible = []

    for channel in enabled_channels():
        if (CHANNELS[channel]["kind"] in {"source-market", "reverse-market"}
                or channel == "v3-dc-o4t-contract") and not channel_healthy(
            channel, require_manifest=True
        ):
            print(f"::warning::{channel}: EVE mail skipped, scan missing/failed/stale; no state change")
            continue
        picked = build_candidates(channel)
        print(f"{channel}: formal candidates={len(picked)}")
        if picked:
            eligible.append((channel, picked))
        else:
            # Do not generate 'zero opportunities' mail or record it as sent.
            print(f"{channel}: no actionable candidates, no game mail")

    for recipient_index, (name, rid) in enumerate(recipients):
        changed = []
        for channel, picked in eligible:
            fresh = pending_candidates(channel, name, picked)
            if not fresh:
                print(f"{channel} skipped for {name}: all TOP{len(picked)} identities already notified")
                continue
            print(f"{channel}: fresh opportunity identities for {name}={len(fresh)}/{len(picked)}")
            changed.append((channel, fresh))
        included, body = compose_digest(changed, stamp)
        if not included:
            print(f"V3 EVE mail: no actionable updates for {name}")
            continue

        subject = f"[V3]捡漏汇总 · {sum(len(v) for _, v in included)}个 · {stamp}"
        channel_key = "v3-consolidated-" + ",".join(ch for ch, _ in included)
        if recipient_index > 0:
            # Avoid a same-second burst against ESI's internal mail rate limit.
            time.sleep(5)
        try:
            send_with_retry(rid, subject, body, channel_key, name)
            for channel, picked in included:
                # Only these IDs were actually displayed in the delivered mail.
                acknowledge_seen(channel, name, picked)
                save_state(channel, name, picked)
            print(f"V3 EVE mail: sent {len(included)} channels to {name} in one message")
        except Exception as exc:
            failures.append((name, exc))
            print(f"::warning::V3 EVE mail failed for {name}; pending channel state preserved: {type(exc).__name__}: {exc}")

    if failures:
        for name, exc in failures:
            print(f"mail failure recipient={name}: {type(exc).__name__}: {exc}")
        raise RuntimeError(f"V3 EVE mail delivery failed for {len(failures)} recipient(s)")


if __name__ == "__main__":
    main()
