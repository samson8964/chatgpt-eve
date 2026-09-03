from pathlib import Path

import pandas as pd

FILES = [
    Path("results/latest/contract_deals_all.csv"),
    Path("results/latest/contract_deals.csv"),
]


def filter_file(path: Path) -> None:
    if not path.exists():
        print(f"reachable filter: skip missing {path}")
        return

    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        print(f"reachable filter: empty {path}")
        return

    if df.empty:
        print(f"reachable filter: no rows in {path}")
        return

    required = {"system_id", "shortest_jumps_to_jita"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"{path} missing reachability columns: {sorted(missing)}")

    system_id = pd.to_numeric(df["system_id"], errors="coerce")
    jumps = pd.to_numeric(df["shortest_jumps_to_jita"], errors="coerce")

    # Conservative rule: only keep locations that resolve to a real solar system
    # and for which ESI can produce a normal stargate route from Jita.
    keep = system_id.notna() & (system_id > 0) & jumps.notna() & (jumps >= 0)

    removed = df.loc[~keep].copy()
    kept = df.loc[keep].copy()
    kept.to_csv(path, index=False)

    print(f"reachable filter: {path} kept={len(kept)} removed={len(removed)}")
    if not removed.empty:
        cols = [c for c in ["contract_id", "system_name", "station_name", "risk_tier", "shortest_jumps_to_jita"] if c in removed.columns]
        print("reachable filter removed examples:")
        print(removed[cols].head(20).to_string(index=False))


def main() -> None:
    for path in FILES:
        filter_file(path)


if __name__ == "__main__":
    main()
