from pathlib import Path
import pandas as pd

BASE = "https://eve-contract-opener.99617224.workers.dev"
LATEST = Path("results/latest")


def add_links(path: Path, contract=False, market=False):
    if not path.exists():
        print(f"skip missing: {path}")
        return
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        print(f"skip empty: {path}")
        return

    if contract and "contract_id" in df.columns:
        ids = pd.to_numeric(df["contract_id"], errors="coerce").astype("Int64")
        df["eve_contract_url"] = ids.map(lambda x: f"{BASE}/c/{x}" if pd.notna(x) else "")

    if market and "product_type_id" in df.columns:
        ids = pd.to_numeric(df["product_type_id"], errors="coerce").astype("Int64")
        df["eve_market_url"] = ids.map(lambda x: f"{BASE}/m/{x}" if pd.notna(x) else "")

    df.to_csv(path, index=False)
    print(f"action links added: {path}")


add_links(LATEST / "ranked_opportunities.csv", contract=True, market=True)
add_links(LATEST / "all_executable_scored.csv", contract=True, market=True)
add_links(LATEST / "product_watchlist.csv", market=True)
