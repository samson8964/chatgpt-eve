from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

from scanner_source import (
    PUBLIC_CONTRACTS_INDEX,
    DATA,
    download,
    fetch_many_ref,
    latest_file,
    load_contracts,
    name_en,
    truthy_series,
)

STATE = Path("results/state/bpc_light_seen_contracts.csv")
LATEST = Path("results/latest/bpc_light_probe.csv")
MAX_CONTRACT_PRICE = float(os.getenv("BPC_LIGHT_MAX_CONTRACT_PRICE", "5000000000"))
MIN_HOURS_TO_EXPIRE = float(os.getenv("BPC_LIGHT_MIN_HOURS_TO_EXPIRE", "2"))


def _write_output(key: str, value: str) -> None:
    path = os.getenv("GITHUB_OUTPUT", "").strip()
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def _load_state() -> pd.DataFrame:
    if not STATE.exists():
        return pd.DataFrame(columns=["contract_id", "first_seen_at", "blueprints"])
    try:
        df = pd.read_csv(STATE)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=["contract_id", "first_seen_at", "blueprints"])
    if "contract_id" not in df.columns:
        return pd.DataFrame(columns=["contract_id", "first_seen_at", "blueprints"])
    df["contract_id"] = pd.to_numeric(df["contract_id"], errors="coerce")
    df = df[df["contract_id"].notna()].copy()
    df["contract_id"] = df["contract_id"].astype("int64")
    return df


def select_light_bpc_contracts(
    contracts: pd.DataFrame,
    items: pd.DataFrame,
    *,
    now: pd.Timestamp | None = None,
    max_contract_price: float = MAX_CONTRACT_PRICE,
    min_hours_to_expire: float = MIN_HOURS_TO_EXPIRE,
) -> pd.DataFrame:
    """Cheap BPC-only contract discovery.

    Deliberately does not fetch market books, manufacturing recipes, factory SCI,
    routes, history, or profitability. Those belong to the deep BPC workflow.
    """
    if contracts.empty or items.empty:
        return pd.DataFrame()

    required_contract = {"contract_id", "type", "price"}
    required_item = {"contract_id", "is_included", "is_blueprint_copy", "type_id", "runs"}
    if not required_contract.issubset(contracts.columns) or not required_item.issubset(items.columns):
        return pd.DataFrame()

    c = contracts.copy()
    c["contract_id"] = pd.to_numeric(c["contract_id"], errors="coerce")
    c["price"] = pd.to_numeric(c["price"], errors="coerce").fillna(0.0)
    c = c[
        c["contract_id"].notna()
        & c["type"].astype(str).eq("item_exchange")
        & (c["price"] > 0)
        & (c["price"] <= float(max_contract_price))
    ].copy()
    if c.empty:
        return pd.DataFrame()

    c["contract_id"] = c["contract_id"].astype("int64")
    now = now if now is not None else pd.Timestamp.now(tz="UTC")

    if "date_expired" in c.columns:
        exp = pd.to_datetime(c["date_expired"], utc=True, errors="coerce")
        hours = (exp - now).dt.total_seconds() / 3600.0
        c = c[exp.isna() | (hours >= float(min_hours_to_expire))].copy()

    # Match the production BPC scanner's fail-closed location policy: public
    # player structures are excluded because access cannot be proven cheaply.
    if "start_location_id" in c.columns:
        start_location = pd.to_numeric(c["start_location_id"], errors="coerce")
        c = c[start_location.isna() | (start_location < 1_000_000_000_000)].copy()

    if c.empty:
        return pd.DataFrame()

    valid_ids = set(c["contract_id"].astype(int).tolist())
    ii = items[items["contract_id"].isin(valid_ids)].copy()
    if ii.empty:
        return pd.DataFrame()

    ii["contract_id"] = pd.to_numeric(ii["contract_id"], errors="coerce")
    ii = ii[ii["contract_id"].notna()].copy()
    ii["contract_id"] = ii["contract_id"].astype("int64")
    ii["_included"] = truthy_series(ii["is_included"])
    ii["_bpc"] = truthy_series(ii["is_blueprint_copy"])

    # Any requested item or any included non-BPC item makes the contract unsuitable
    # for the BPC manufacturing lane.
    bad_requested = set(ii.loc[~ii["_included"], "contract_id"].astype(int).tolist())
    bad_extra = set(ii.loc[ii["_included"] & ~ii["_bpc"], "contract_id"].astype(int).tolist())

    bpc = ii[ii["_included"] & ii["_bpc"]].copy()
    for col, default in [
        ("type_id", 0),
        ("runs", 0),
        ("quantity", 1),
        ("material_efficiency", 0),
        ("time_efficiency", 0),
    ]:
        if col not in bpc.columns:
            bpc[col] = default
        bpc[col] = pd.to_numeric(bpc[col], errors="coerce").fillna(default).astype(int)

    bpc = bpc[(bpc["type_id"] > 0) & (bpc["runs"] > 0)].copy()
    good_ids = set(bpc["contract_id"].astype(int).tolist()) - bad_requested - bad_extra
    if not good_ids:
        return pd.DataFrame()

    c = c[c["contract_id"].isin(good_ids)].copy()
    bpc = bpc[bpc["contract_id"].isin(good_ids)].copy()

    grouped = []
    for cid, rows in bpc.groupby("contract_id", sort=False):
        specs = []
        total_runs = 0
        for r in rows.itertuples(index=False):
            copies = max(1, int(getattr(r, "quantity", 1)))
            runs = int(getattr(r, "runs", 0))
            me = int(getattr(r, "material_efficiency", 0))
            te = int(getattr(r, "time_efficiency", 0))
            tid = int(getattr(r, "type_id", 0))
            total_runs += copies * runs
            specs.append({
                "type_id": tid,
                "copies": copies,
                "runs": runs,
                "me": me,
                "te": te,
            })
        grouped.append({
            "contract_id": int(cid),
            "bpc_count": int(len(rows)),
            "total_bpc_runs": int(total_runs),
            "_specs": specs,
        })

    meta = pd.DataFrame(grouped)
    out = c.merge(meta, on="contract_id", how="inner")
    return out.sort_values(["contract_id"], ascending=False).reset_index(drop=True)


def _decorate_blueprints(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    type_ids = {
        int(spec["type_id"])
        for specs in df["_specs"]
        for spec in specs
        if int(spec.get("type_id", 0)) > 0
    }
    type_objs = fetch_many_ref("types", type_ids) if type_ids else {}

    def describe(specs) -> str:
        parts = []
        for s in specs:
            tid = int(s["type_id"])
            nm = name_en(type_objs.get(tid), str(tid))
            copies = int(s["copies"])
            parts.append(
                f"{copies}x {nm} [{int(s['runs'])} runs, ME{int(s['me'])}/TE{int(s['te'])}]"
            )
        return " | ".join(parts)

    out = df.copy()
    out["blueprints"] = out["_specs"].apply(describe)
    return out.drop(columns=["_specs"], errors="ignore")


def probe() -> int:
    url, modified = latest_file(PUBLIC_CONTRACTS_INDEX)
    archive = DATA / Path(url).name
    if not archive.exists():
        download(url, archive)

    contracts, items = load_contracts(archive)
    current = select_light_bpc_contracts(contracts, items)
    current_ids = set(current.get("contract_id", pd.Series(dtype="int64")).astype(int).tolist())
    state = _load_state()

    # First run is baseline-only. This is intentional: switching probe
    # implementations must not cause every existing BPC contract to launch a deep scan.
    if not STATE.exists():
        decorated = _decorate_blueprints(current)
        now = pd.Timestamp.now(tz="UTC").isoformat()
        STATE.parent.mkdir(parents=True, exist_ok=True)
        baseline = decorated[[c for c in ["contract_id", "blueprints"] if c in decorated.columns]].copy()
        baseline["first_seen_at"] = now
        baseline = baseline[["contract_id", "first_seen_at", "blueprints"]]
        baseline.to_csv(STATE, index=False)
        LATEST.parent.mkdir(parents=True, exist_ok=True)
        decorated.head(0).to_csv(LATEST, index=False)
        print(
            f"BPC light probe baseline: current={len(current_ids)} contracts; "
            f"dataset={modified}; no deep dispatch"
        )
        _write_output("trigger_deep", "false")
        _write_output("new_count", "0")
        _write_output("new_ids", "")
        return 0

    seen = set(state["contract_id"].astype(int).tolist())
    fresh = current[~current["contract_id"].isin(seen)].copy()
    fresh = _decorate_blueprints(fresh)
    LATEST.parent.mkdir(parents=True, exist_ok=True)
    fresh.drop(columns=["_specs"], errors="ignore").to_csv(LATEST, index=False)

    ids = ",".join(str(int(x)) for x in fresh.get("contract_id", pd.Series(dtype="int64")).tolist())
    print(
        f"BPC light probe: current={len(current_ids)} seen={len(seen)} new={len(fresh)} "
        f"dataset={modified}"
    )
    if not fresh.empty:
        for _, r in fresh.head(20).iterrows():
            print(
                f"new BPC contract {int(r['contract_id'])}: price={float(r.get('price', 0))/1e6:.1f}M "
                f"runs={int(r.get('total_bpc_runs', 0))} {str(r.get('blueprints', ''))[:300]}"
            )

    _write_output("trigger_deep", "true" if len(fresh) else "false")
    _write_output("new_count", str(len(fresh)))
    _write_output("new_ids", ids)
    return 0


def ack(ids_raw: str) -> int:
    ids = sorted({int(x) for x in str(ids_raw).split(",") if str(x).strip().isdigit()})
    if not ids:
        print("BPC light probe ack: no ids")
        return 0

    state = _load_state()
    seen = set(state["contract_id"].astype(int).tolist()) if not state.empty else set()
    now = pd.Timestamp.now(tz="UTC").isoformat()

    latest = pd.DataFrame()
    if LATEST.exists():
        try:
            latest = pd.read_csv(LATEST)
        except pd.errors.EmptyDataError:
            pass

    rows = state.to_dict("records") if not state.empty else []
    for cid in ids:
        if cid in seen:
            continue
        blueprints = ""
        if not latest.empty and "contract_id" in latest.columns:
            match = latest[pd.to_numeric(latest["contract_id"], errors="coerce").eq(cid)]
            if not match.empty:
                blueprints = str(match.iloc[0].get("blueprints", "") or "")
        rows.append({"contract_id": cid, "first_seen_at": now, "blueprints": blueprints})

    out = pd.DataFrame(rows, columns=["contract_id", "first_seen_at", "blueprints"])
    if not out.empty:
        out.drop_duplicates(subset=["contract_id"], keep="first", inplace=True)
        out.sort_values("first_seen_at", ascending=False, inplace=True)
        out = out.head(20000)

    STATE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(STATE, index=False)
    print(f"BPC light probe ack: added={len(set(ids) - seen)} total={len(out)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ack", default="", help="comma-separated contract ids whose deep scan was dispatched")
    args = parser.parse_args()
    if args.ack:
        return ack(args.ack)
    return probe()


if __name__ == "__main__":
    raise SystemExit(main())
