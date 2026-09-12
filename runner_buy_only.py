from __future__ import annotations

import ast
import os
from pathlib import Path

# Configure runner.py before importing it. Revenue remains current Jita buy depth, while
# immediate sale into a buy order has no sell-order broker/relist charge.
os.environ.setdefault("MARKET_BROKER_FEE_RATE", "0")
os.environ.setdefault("EXPECTED_RELISTS", "0")
os.environ.setdefault("DEAL_MAX_CONTRACT_PRICE", "5000000000")

import runner


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        raise RuntimeError(f"Buy-only BPC patch anchor missing: {label}")
    return source.replace(old, new, 1)


def apply_policy(source: str) -> str:
    # Make the contract cap available inside the dynamically executed scanner.
    source = replace_once(
        source,
        'MIN_HOURS_TO_EXPIRE = float(os.getenv("MIN_HOURS_TO_EXPIRE", "2"))\n',
        'MIN_HOURS_TO_EXPIRE = float(os.getenv("MIN_HOURS_TO_EXPIRE", "2"))\n'
        'MAX_CONTRACT_PRICE = float(os.getenv("DEAL_MAX_CONTRACT_PRICE", "5000000000"))\n',
        "max contract setting",
    )

    source = replace_once(
        source,
        '    c = contracts[(contracts["type"] == "item_exchange") & (contracts["price"] > 0)].copy()\n',
        '    c = contracts[(contracts["type"] == "item_exchange") & (contracts["price"] > 0) & (contracts["price"] <= MAX_CONTRACT_PRICE)].copy()\n',
        "BPC contract price cap",
    )

    # type_objs/group_objs already exist here. Filter SKIN/SKINR licences, nanocoatings and
    # design-element production before candidates can consume PREFILTER_TOP slots.
    source = replace_once(
        source,
        '    print("5) prefilter")\n',
        '    SKIN_KEYWORDS=(" skin","skin ","skinr","nanocoating","sequencing binder","design element","pattern projection","pattern projector","holographic")\n'
        '    def _skin_related_type(tid):\n'
        '        obj=type_objs.get(int(tid))\n'
        '        nm=(name_en(obj,"") or "").strip().lower()\n'
        '        gid=type_group_id(obj)\n'
        '        gn=(name_en(group_objs.get(gid),"") or "").strip().lower() if gid is not None else ""\n'
        '        text=" "+nm+" "+gn+" "\n'
        '        return any(k in text for k in SKIN_KEYWORDS)\n\n'
        '    print("5) prefilter")\n',
        "SKIN helper",
    )

    # This anchor is the post-runner.patch_source version because the stock runner already inserts
    # its fast single-product check at this point.
    source = replace_once(
        source,
        '        if len(prodq) != 1:\n'
        '            excluded.append({"contract_id":cid,"reason":"MULTI_PRODUCT_BPC_PACK_SKIPPED_FAST_MODE"}); continue\n'
        '        classes = {product_class.get(int(tid), "normal") for tid in prodq}\n',
        '        if len(prodq) != 1:\n'
        '            excluded.append({"contract_id":cid,"reason":"MULTI_PRODUCT_BPC_PACK_SKIPPED_FAST_MODE"}); continue\n'
        '        related_ids=set(prodq.keys()) | {int(j["bp_tid"]) for j in jobs}\n'
        '        if any(_skin_related_type(tid) for tid in related_ids):\n'
        '            excluded.append({"contract_id":cid,"reason":"SKIN_OR_SKINR_RELATED"}); continue\n'
        '        classes = {product_class.get(int(tid), "normal") for tid in prodq}\n',
        "SKIN prefilter",
    )
    return source


def main():
    path = Path("scanner_source.py")
    source = path.read_text(encoding="utf-8")
    source = runner.patch_source(source)
    source = apply_policy(source)

    tree = ast.parse(source, filename="scanner_buy_only.py")
    tree = runner.ScoreRowIntGuard().visit(tree)
    ast.fix_missing_locations(tree)
    print(
        "BPC Buy-Only scanner: contract<=5B, SKIN/SKINR excluded before prefilter, "
        "product revenue=current Jita buy depth, broker/relist=0."
    )
    exec(
        compile(tree, "scanner_buy_only.py", "exec"),
        {"__name__": "__main__", "__safe_int": runner.safe_int},
    )


if __name__ == "__main__":
    main()
