from pathlib import Path
import pandas as pd

SOURCE = Path('results/latest/ranked_opportunities_v2.csv')
OUT = Path('results/latest/bpc_v2_safe_candidates.csv')


def main():
    if not SOURCE.exists():
        raise RuntimeError(f'missing input: {SOURCE}')
    df = pd.read_csv(SOURCE)
    if df.empty:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(OUT, index=False)
        print('BPC V2 SAFE export: 0 rows')
        return

    required = ['v2_status', 'v2_live_net_profit', 'v2_live_net_roi', 'v2_stress_net_profit', 'v2_orderbook_complete']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f'missing required columns: {missing}')

    safe = df[df['v2_status'].astype(str).eq('SAFE')].copy()
    safe = safe[pd.to_numeric(safe['v2_live_net_profit'], errors='coerce').fillna(0) >= 20_000_000]
    safe = safe[pd.to_numeric(safe['v2_live_net_roi'], errors='coerce').fillna(0) >= 0.10]
    safe = safe[pd.to_numeric(safe['v2_stress_net_profit'], errors='coerce').fillna(0) > 0]
    safe = safe[safe['v2_orderbook_complete'].astype(bool)]

    sort_cols = [c for c in ['v2_score', 'v2_live_net_profit'] if c in safe.columns]
    if sort_cols:
        safe.sort_values(sort_cols, ascending=[False] * len(sort_cols), inplace=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    safe.to_csv(OUT, index=False)
    print(f'BPC V2 SAFE export: {len(safe)} rows -> {OUT}')


if __name__ == '__main__':
    main()
