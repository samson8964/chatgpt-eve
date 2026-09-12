from __future__ import annotations

import ast
import os
from pathlib import Path

# Configure runner.py before importing it. Revenue remains current Jita buy depth, while
# immediate sale into a buy order has no sell-order broker/relist charge.
os.environ.setdefault("MARKET_BROKER_FEE_RATE", "0")
os.environ.setdefault("EXPECTED_RELISTS", "0")
os.environ.setdefault("DEAL_MAX_CONTRACT_PRICE", "5000000000")
# Keep the best 500 cheap-economics candidates for the expensive manufacturing quote pass.
os.environ.setdefault("PREFILTER_TOP", "500")

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

    # type_objs/group_objs already exist here. Filter SKIN/SKINR licences, capital hulls and
    # actual structures before any candidate can consume one of the PREFILTER_TOP exact-pass slots.
    source = replace_once(
        source,
        '    print("5) prefilter")\n',
        '    SKIN_KEYWORDS=(" skin","skin ","skinr","nanocoating","sequencing binder","design element","pattern projection","pattern projector","holographic")\n'
        '    CAPITAL_HULL_GROUPS={"carrier","dreadnought","force auxiliary","capital industrial ship","lancer dreadnought","supercarrier","titan","freighter","jump freighter"}\n'
        '    STRUCTURE_GROUP_KEYWORDS=("citadel","engineering complex","refinery","flex structure","control tower","assembly array","mobile laboratory","corporate hangar array","storage silo","reactor array","moon mining","sovereignty structure","orbital infrastructure","orbital construction platform")\n'
        '    STRUCTURE_CATEGORY_IDS={23,40,46,65}\n'
        '    def _group_obj_for_type(tid):\n'
        '        obj=type_objs.get(int(tid))\n'
        '        gid=type_group_id(obj)\n'
        '        return obj, gid, group_objs.get(gid) if gid is not None else None\n\n'
        '    def _skin_related_type(tid):\n'
        '        obj,gid,gobj=_group_obj_for_type(tid)\n'
        '        nm=(name_en(obj,"") or "").strip().lower()\n'
        '        gn=(name_en(gobj,"") or "").strip().lower()\n'
        '        text=" "+nm+" "+gn+" "\n'
        '        return any(k in text for k in SKIN_KEYWORDS)\n\n'
        '    def _capital_hull_or_structure(tid):\n'
        '        obj,gid,gobj=_group_obj_for_type(tid)\n'
        '        gn=(name_en(gobj,"") or "").strip().lower()\n'
        '        if gn in CAPITAL_HULL_GROUPS:\n'
        '            return "CAPITAL_HULL"\n'
        '        cat=0\n'
        '        if isinstance(gobj,dict):\n'
        '            try: cat=int(gobj.get("category_id") or gobj.get("categoryID") or 0)\n'
        '            except Exception: cat=0\n'
        '        if cat in STRUCTURE_CATEGORY_IDS or any(k in gn for k in STRUCTURE_GROUP_KEYWORDS):\n'
        '            return "STRUCTURE_HULL"\n'
        '        return ""\n\n'
        '    print("5) prefilter")\n',
        "exclusion helpers",
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
        '        product_exclusions=[_capital_hull_or_structure(tid) for tid in prodq]\n'
        '        if any(x=="CAPITAL_HULL" for x in product_exclusions):\n'
        '            excluded.append({"contract_id":cid,"reason":"CAPITAL_HULL_BLUEPRINT_EXCLUDED"}); continue\n'
        '        if any(x=="STRUCTURE_HULL" for x in product_exclusions):\n'
        '            excluded.append({"contract_id":cid,"reason":"STRUCTURE_BLUEPRINT_EXCLUDED"}); continue\n'
        '        classes = {product_class.get(int(tid), "normal") for tid in prodq}\n',
        "SKIN/capital/structure prefilter",
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
        "BPC Buy-Only scanner: exact-pass top500, contract<=5B, SKIN/SKINR + capital hull + structure hull excluded before prefilter, "
        "product revenue=current Jita buy depth, broker/relist=0."
    )
    exec(
        compile(tree, "scanner_buy_only.py", "exec"),
        {"__name__": "__main__", "__safe_int": runner.safe_int},
    )


if __name__ == "__main__":
    main()
