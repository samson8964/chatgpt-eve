from __future__ import annotations

import ast
import os
from pathlib import Path

# Keep V3.1 isolated from production. It uses the exact same economic model as
# runner_buy_only.py, but prefetches unique industry-cost quotes concurrently.
os.environ.setdefault("MARKET_BROKER_FEE_RATE", "0")
os.environ.setdefault("EXPECTED_RELISTS", "0")
os.environ.setdefault("DEAL_MAX_CONTRACT_PRICE", "5000000000")
os.environ.setdefault("PREFILTER_TOP", "500")
os.environ.setdefault("V31_INDUSTRY_WORKERS", "10")

import runner
import runner_buy_only


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        raise RuntimeError(f"V3.1 performance patch anchor missing: {label}")
    return source.replace(old, new, 1)


def apply_v31_performance(source: str) -> str:
    # The production scanner performs industry-cost HTTP calls serially inside
    # candidate -> factory -> job loops. V3.1 builds the exact same quote keys
    # first, de-duplicates them, then fetches those independent quotes in parallel.
    # The later economics loop only reads this cache, so valuation semantics stay
    # unchanged.
    source = replace_once(
        source,
        '    print("6) exact fees")\n',
        '    print("5c) V3.1 parallel industry quote prefetch")\n'
        '    quote_specs={}\n'
        '    for p in prelim:\n'
        '        for fac in factories:\n'
        '            for j in p["jobs"]:\n'
        '                key=(int(j["bp_tid"]),int(j["product_tid"]),int(j["runs"]),int(j["me"]),int(j["te"]),int(fac["system_id"]))\n'
        '                quote_specs[key]=key\n'
        '    quote_cache={}\n'
        '    if quote_specs:\n'
        '        quote_workers=min(max(1,int(os.getenv("V31_INDUSTRY_WORKERS","10"))),len(quote_specs))\n'
        '        with ThreadPoolExecutor(max_workers=quote_workers) as ex:\n'
        '            futs={ex.submit(industry_quote,*spec):key for key,spec in quote_specs.items()}\n'
        '            for fut in as_completed(futs):\n'
        '                key=futs[fut]\n'
        '                try: quote_cache[key]=fut.result()\n'
        '                except Exception: quote_cache[key]=None\n'
        '    quote_ok=sum(1 for q in quote_cache.values() if q)\n'
        '    print(f"5c) unique industry quotes={len(quote_specs)} ok={quote_ok} workers={min(max(1,int(os.getenv(\'V31_INDUSTRY_WORKERS\',\'10\'))),max(1,len(quote_specs)))}")\n\n'
        '    print("6) exact fees")\n',
        "parallel industry quote prefetch",
    )

    source = replace_once(
        source,
        '                q=industry_quote(j["bp_tid"],j["product_tid"],j["runs"],j["me"],j["te"],fac["system_id"])\n',
        '                q=quote_cache.get((int(j["bp_tid"]),int(j["product_tid"]),int(j["runs"]),int(j["me"]),int(j["te"]),int(fac["system_id"])))\n',
        "industry quote cache lookup",
    )
    return source


def main():
    source = Path("scanner_source.py").read_text(encoding="utf-8")
    source = runner.patch_source(source)
    source = runner_buy_only.apply_policy(source)
    source = apply_v31_performance(source)

    tree = ast.parse(source, filename="scanner_buy_only_v31.py")
    tree = runner.ScoreRowIntGuard().visit(tree)
    ast.fix_missing_locations(tree)

    print(
        "Opportunity Engine V3.1 BPC scanner: production-equivalent buy-only economics "
        "with de-duplicated parallel industry-cost quote prefetch; no production mail."
    )
    exec(
        compile(tree, "scanner_buy_only_v31.py", "exec"),
        {"__name__": "__main__", "__safe_int": runner.safe_int},
    )


if __name__ == "__main__":
    main()
