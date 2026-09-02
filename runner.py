import ast
import math
import os
from pathlib import Path

# Fast/actionable defaults. They can still be overridden from GitHub Actions env.
os.environ.setdefault("MIN_NET_PROFIT", "10000000")
os.environ.setdefault("MIN_NET_ROI", "0.08")
os.environ.setdefault("PREFILTER_TOP", "150")
os.environ.setdefault("HIGHSEC_FACTORY_CANDIDATES", "2")
os.environ.setdefault("PREFILTER_MIN_GROSS_REVENUE", "30000000")
os.environ.setdefault("PREFILTER_MIN_ROI", "0.05")
os.environ.setdefault("PREFILTER_MAX_OUTPUT_DAYS_30D", "2.0")


def safe_int(value):
    try:
        if value is None:
            return 0
        number = float(value)
        if not math.isfinite(number):
            return 0
        return int(number)
    except (TypeError, ValueError, OverflowError):
        return 0


class ScoreRowIntGuard(ast.NodeTransformer):
    """Harden one-argument int(...) calls inside scoring/classification only."""

    def __init__(self):
        self.in_guarded_function = False

    def visit_FunctionDef(self, node):
        previous = self.in_guarded_function
        if node.name in {"score_row", "classify_row"}:
            self.in_guarded_function = True
        self.generic_visit(node)
        self.in_guarded_function = previous
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        if (
            self.in_guarded_function
            and isinstance(node.func, ast.Name)
            and node.func.id == "int"
            and len(node.args) == 1
            and not node.keywords
        ):
            node.func = ast.copy_location(ast.Name(id="__safe_int", ctx=ast.Load()), node.func)
        return node


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        raise RuntimeError(f"Fast scanner patch anchor missing: {label}")
    return source.replace(old, new, 1)


def patch_source(source: str) -> str:
    # Add fast-prefilter controls next to the existing strategy settings.
    source = replace_once(
        source,
        'PREFILTER_TOP = int(os.getenv("PREFILTER_TOP", "800"))\n',
        'PREFILTER_TOP = int(os.getenv("PREFILTER_TOP", "800"))\n'
        'PREFILTER_MIN_GROSS_REVENUE = float(os.getenv("PREFILTER_MIN_GROSS_REVENUE", "30000000"))\n'
        'PREFILTER_MIN_ROI = float(os.getenv("PREFILTER_MIN_ROI", "0.05"))\n'
        'PREFILTER_MAX_OUTPUT_DAYS_30D = float(os.getenv("PREFILTER_MAX_OUTPUT_DAYS_30D", "2.0"))\n',
        "prefilter settings",
    )

    # Multi-product BPC packs are expensive to value and hard to liquidate cleanly.
    source = replace_once(
        source,
        '        if not ok or not matq or not prodq: continue\n        classes = {product_class.get(int(tid), "normal") for tid in prodq}\n',
        '        if not ok or not matq or not prodq: continue\n'
        '        if len(prodq) != 1:\n'
        '            excluded.append({"contract_id":cid,"reason":"MULTI_PRODUCT_BPC_PACK_SKIPPED_FAST_MODE"}); continue\n'
        '        classes = {product_class.get(int(tid), "normal") for tid in prodq}\n',
        "single-product filter",
    )

    # Cheap economics filter before any manufacturing-cost API calls.
    source = replace_once(
        source,
        '        cp=float(cm.get("price",0) or 0)\n'
        '        if revenue - cp - material_cost < MIN_NET_PROFIT: continue\n'
        '        haul_m3 = sum(type_volume(type_objs.get(tid))*qty for tid,qty in matq.items()) + sum(type_volume(type_objs.get(tid))*qty for tid,qty in prodq.items())\n',
        '        cp=float(cm.get("price",0) or 0)\n'
        '        rough_profit = revenue - cp - material_cost\n'
        '        rough_base = cp + material_cost\n'
        '        rough_roi = rough_profit / rough_base if rough_base else 0.0\n'
        '        if revenue < PREFILTER_MIN_GROSS_REVENUE:\n'
        '            excluded.append({"contract_id":cid,"reason":"BATCH_VALUE_BELOW_FAST_FLOOR"}); continue\n'
        '        if rough_profit < MIN_NET_PROFIT: continue\n'
        '        if rough_roi < PREFILTER_MIN_ROI:\n'
        '            excluded.append({"contract_id":cid,"reason":"ROUGH_ROI_BELOW_FAST_FLOOR"}); continue\n'
        '        haul_m3 = sum(type_volume(type_objs.get(tid))*qty for tid,qty in matq.items()) + sum(type_volume(type_objs.get(tid))*qty for tid,qty in prodq.items())\n',
        "cheap economics filter",
    )

    # Add a quick 30d-liquidity pass before the slow exact manufacturing quotes.
    source = replace_once(
        source,
        '    prelim.sort(key=lambda x: x["gross_revenue"]-x["contract_price"]-x["material_cost"], reverse=True)\n'
        '    prelim = prelim[:PREFILTER_TOP]\n\n'
        '    print("6) exact fees")\n',
        '    prelim.sort(key=lambda x: x["gross_revenue"]-x["contract_price"]-x["material_cost"], reverse=True)\n'
        '    prelim = prelim[:PREFILTER_TOP]\n'
        '    print(f"5a) economic prefilter kept {len(prelim)} candidates")\n\n'
        '    print("5b) quick liquidity")\n'
        '    quick_histories = {}\n'
        '    quick_tids = sorted({int(next(iter(p["prodq"].keys()))) for p in prelim})\n'
        '    with ThreadPoolExecutor(max_workers=min(WORKERS,8)) as ex:\n'
        '        futs={ex.submit(market_history,tid):tid for tid in quick_tids}\n'
        '        for fut in as_completed(futs):\n'
        '            tid=futs[fut]\n'
        '            try: quick_histories[tid]=fut.result()\n'
        '            except Exception: quick_histories[tid]={}\n'
        '    liquid_prelim=[]\n'
        '    for p in prelim:\n'
        '        tid, qty = next(iter(p["prodq"].items()))\n'
        '        avg30 = float(quick_histories.get(int(tid),{}).get("avg_daily_volume_30d",0) or 0)\n'
        '        if avg30 <= 0:\n'
        '            excluded.append({"contract_id":p["contract_id"],"reason":"NO_30D_MARKET_VOLUME"}); continue\n'
        '        if float(qty) / avg30 > PREFILTER_MAX_OUTPUT_DAYS_30D:\n'
        '            excluded.append({"contract_id":p["contract_id"],"reason":"BATCH_TOO_LARGE_VS_30D_VOLUME"}); continue\n'
        '        liquid_prelim.append(p)\n'
        '    prelim=liquid_prelim\n'
        '    print(f"5b) liquidity prefilter kept {len(prelim)} candidates")\n\n'
        '    print("6) exact fees")\n',
        "liquidity prefilter",
    )

    # Reuse quick history results later instead of calling the same ESI endpoint twice.
    source = replace_once(
        source,
        '    histories={}\n'
        '    tids=sorted({int(x) for x in df.loc[df["is_single_product"],"product_type_id"].dropna().tolist()})\n',
        '    histories=dict(quick_histories) if "quick_histories" in locals() else {}\n'
        '    tids=sorted({int(x) for x in df.loc[df["is_single_product"],"product_type_id"].dropna().tolist()} - set(histories))\n',
        "history reuse",
    )

    return source


def main():
    source_path = Path("scanner_source.py")
    if not source_path.exists():
        raise RuntimeError("scanner_source.py is missing")

    source = patch_source(source_path.read_text(encoding="utf-8"))
    tree = ast.parse(source, filename="scanner_fast.py")
    tree = ScoreRowIntGuard().visit(tree)
    ast.fix_missing_locations(tree)

    print(
        "Fast scanner enabled: gross>=30M, rough ROI>=5%, single product, "
        "<=2 days 30d volume, top150, 2 factory candidates, final ROI>=8%."
    )
    exec(
        compile(tree, "scanner_fast.py", "exec"),
        {"__name__": "__main__", "__safe_int": safe_int},
    )


if __name__ == "__main__":
    main()
