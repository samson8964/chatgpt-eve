"""V4 independent full-universe scanner, initial READ-ONLY census stage.

Executes a fresh full-market and full-public-contract ingestion on EVERY invocation.
Applies an unbounded optimistic initial screen across every market location/type.
NEVER sends mail from this module, and NEVER calls V2/V3 code.
A census is not a completed execution-proof pipeline; it reports this honestly.
"""
from __future__ import annotations
import argparse
import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from v4.sources import (MARKET_INDEX, CONTRACT_INDEX, SourceError, SnapshotStale, advertised,
                        download_fresh, market_dataframe, contract_dataframes)


def naive_upper_bound_universe(market: pd.DataFrame, floor: float = 50_000_000) -> dict:
    """FULL scan, group every station & type; intentionally no top-N truncation.

    This is discovery only, not a valid execution proof. For proof the new order
    validator needs full depth, seller skills, realistic taxes, access and haul.
    Optimistic bound never decreases true potential profitable volume: using the
    best unit spread and all source-side units gives an overestimate.
    """
    cols = ['location_id', 'type_id', 'is_buy_order', 'price', 'volume_remain']
    df = market[cols].copy()
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    df['volume_remain'] = pd.to_numeric(df['volume_remain'], errors='coerce').fillna(0)
    df['location_id'] = pd.to_numeric(df['location_id'], errors='coerce').fillna(0).astype('int64')
    df['type_id'] = pd.to_numeric(df['type_id'], errors='coerce').fillna(0).astype('int64')
    flag = df['is_buy_order']
    is_buy = flag if flag.dtype == bool else flag.fillna(False).astype(str).str.lower().isin(('true', '1', 't'))
    good = (df['price'] > 0) & df['price'].notna() & (df['volume_remain'] > 0) & (df['type_id'] > 0) & (df['location_id'] > 0)
    sells = df[good & ~is_buy]
    buys = df[good & is_buy]
    if sells.empty or buys.empty:
        raise SourceError('NO_USABLE_TWO_SIDED_MARKET')
    source = sells.groupby(['location_id', 'type_id'], sort=False).agg(
        min_ask=('price', 'min'), total_sell=('volume_remain','sum')).reset_index()
    # Global best buy ANYWHERE -- not only Jita, no omitted locations.
    global_buy = buys.groupby('type_id', sort=False).agg(max_bid=('price','max')).reset_index()
    candidates = source.merge(global_buy, on='type_id', how='left', validate='many_to_one')
    spread = (candidates['max_bid'] - candidates['min_ask']).clip(lower=0)
    possible_gross_profit = spread * candidates['total_sell']
    contenders = candidates[possible_gross_profit >= floor]
    return {
        'market_raw_rows': int(len(df)),
        'market_valid_rows': int(good.sum()),
        'sell_order_rows': int(len(sells)),
        'buy_order_rows': int(len(buys)),
        'market_locations': int(df.loc[good,'location_id'].nunique()),
        'market_types': int(df.loc[good,'type_id'].nunique()),
        'source_location_type_pairs': int(len(source)),
        'optimistic_initial_candidates': int(len(contenders)),
        'precheck_all_pairs_covered': True,
        'precheck_definition': 'unbounded_global-best-bid upper bound before fees/route/risk',
        'deep_verified': 0,
        'reason': 'Full coverage discovery complete; execution-proof modules pending.'
    }


def run(output: Path, data_dir: Path, *, max_market_age_h: float=2,
        max_contract_age_h: float=3) -> dict:
    run_id = 'v4-' + uuid.uuid4().hex
    report = dict(run_id=run_id, started_at=datetime.now(timezone.utc).isoformat(),
                  version='V4-initial-readonly', sources={}, overall='FAILED',
                  live_mail_allowed=False, execution_proof_complete=False)
    try:
        # Verify BOTH advertised snapshot timestamps before downloading any
        # files. A delayed publisher is a safe, expected skip; not a crash.
        # Never download stale data or mix one fresh and one stale generation.
        required = (
            ('market_orders', MARKET_INDEX,max_market_age_h,'.csv.bz2'),
            ('public_contracts', CONTRACT_INDEX,max_contract_age_h,'.tar.bz2'))
        available = {}
        for name,index,limit,suffix in required:
            try:
                source=advertised(index,max_age_hours=limit)
                available[name]=source
                report['sources'][name]=dict(source,status='FRESH_ADVERTISED')
            except SnapshotStale as exc:
                report['sources'][name]=dict(
                    status='STALE',error=str(exc),
                    age_hours=round(exc.age_hours,3),
                    threshold_hours=exc.threshold_hours,
                    last_modified=exc.last_modified)
            except Exception as exc:
                report['sources'][name]=dict(status='FAILED',error=str(exc))
        outcomes={name:record['status'] for name,record in report['sources'].items()}
        if 'FAILED' in outcomes.values():
            report['overall']='FAILED_SOURCE_COVERAGE'
            return report
        if 'STALE' in outcomes.values():
            report['overall']='SKIPPED_UPSTREAM_STALE'
            report['skip_reason']='UPSTREAM_PUBLIC_SNAPSHOT_NOT_FRESH'
            report['next_action']='WAIT_FOR_PUBLISHER_AND_RECHECK_NEXT_SCHEDULE'
            return report
        for name,index,limit,suffix in required:
            try:
                report['sources'][name]=download_fresh(
                    available[name],data_dir/(name+suffix))
                report['sources'][name]['status']='COMPLETE'
            except Exception as exc:
                report['sources'][name]=dict(
                    available[name],status='FAILED',error=str(exc))
        if any(row['status'] != 'COMPLETE' for row in report['sources'].values()):
            report['overall']='FAILED_SOURCE_COVERAGE'
            return report
        market = market_dataframe(Path(report['sources']['market_orders']['local_file']))
        contracts,items=contract_dataframes(Path(report['sources']['public_contracts']['local_file']))
        report['market']=naive_upper_bound_universe(market)
        report['contracts']={'contract_rows_total':int(len(contracts)),
            'contract_ids_distinct':int(contracts['contract_id'].nunique()),
            'contract_item_rows_total':int(len(items)),
            'all_contracts_included_in_census':True,
            'deep_verified':0}
        # Full source *ingestion* completed. V4 transaction proof and market
        # instance keys not yet generated; do not call this "fully operational".
        report['overall']='CENSUS_COMPLETE_PROOFS_NOT_READY'
        return report
    except Exception as exc:
        report['overall']='FAILED_VALIDATION'
        report['error']=str(exc)
        return report
    finally:
        output.parent.mkdir(parents=True,exist_ok=True)
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output', default='v4_output/latest/full_market_report.json')
    p.add_argument('--data-dir', default='/tmp/v4-market')
    p.add_argument('--max-market-age-hours',type=float,default=2)
    p.add_argument('--max-contract-age-hours',type=float,default=3)
    args=p.parse_args()
    r=run(Path(args.output),Path(args.data_dir),
          max_market_age_h=args.max_market_age_hours,
          max_contract_age_h=args.max_contract_age_hours)
    print(json.dumps({key:val for key,val in r.items() if key not in ('sources',)},ensure_ascii=False,indent=2))
    if r['overall'] not in ('CENSUS_COMPLETE_PROOFS_NOT_READY',
                            'SKIPPED_UPSTREAM_STALE'):
        raise SystemExit('V4 full market census failed: '+r['overall'])


if __name__=='__main__':
    main()
