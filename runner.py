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

# Conservative fully-loaded market-cost model.
# Broker Relations V with zero Caldari/Caldari Navy standings is 1.5% in an NPC station.
# Advanced Broker Relations V gives an 80% relist discount; reserve two downward reprices.
os.environ.setdefault("MARKET_BROKER_FEE_RATE", "0.015")
os.environ.setdefault("ADV_BROKER_RELATIONS_LEVEL", "5")
os.environ.setdefault("EXPECTED_RELISTS", "2")


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
    # Add fast-prefilter and fully-loaded fee controls next to the existing settings.
    source = replace_once(
        source,
        'PREFILTER_TOP = int(os.getenv("PREFILTER_TOP", "800"))\n',
        'PREFILTER_TOP = int(os.getenv("PREFILTER_TOP", "800"))\n'
        'PREFILTER_MIN_GROSS_REVENUE = float(os.getenv("PREFILTER_MIN_GROSS_REVENUE", "30000000"))\n'
        'PREFILTER_MIN_ROI = float(os.getenv("PREFILTER_MIN_ROI", "0.05"))\n'
        'PREFILTER_MAX_OUTPUT_DAYS_30D = float(os.getenv("PREFILTER_MAX_OUTPUT_DAYS_30D", "2.0"))\n'
        'MARKET_BROKER_FEE_RATE = float(os.getenv("MARKET_BROKER_FEE_RATE", "0.015"))\n'
        'ADV_BROKER_RELATIONS_LEVEL = int(os.getenv("ADV_BROKER_RELATIONS_LEVEL", "5"))\n'
        'EXPECTED_RELISTS = int(os.getenv("EXPECTED_RELISTS", "2"))\n'
        'RELIST_DISCOUNT = min(0.80, 0.50 + 0.06 * ADV_BROKER_RELATIONS_LEVEL)\n'
        'RELIST_RESERVE_RATE = MARKET_BROKER_FEE_RATE * (1.0 - RELIST_DISCOUNT) * EXPECTED_RELISTS\n',
        "prefilter and fee settings",
    )

    # Return the industry cost components. total_job_cost already includes SCI + facility tax + SCC,
    # so SCC is exposed for reporting but must not be subtracted a second time.
    source = replace_once(
        source,
        '        return {"job_cost": float(row.get("total_job_cost", 0.0)), "time_hours": parse_iso_hours(row.get("time"))}\n',
        '        return {\n'
        '            "job_cost": float(row.get("total_job_cost", 0.0)),\n'
        '            "time_hours": parse_iso_hours(row.get("time")),\n'
        '            "scc_surcharge": float(row.get("scc_surcharge", 0.0)),\n'
        '            "facility_tax_cost": float(row.get("facility_tax", 0.0)),\n'
        '            "system_cost_index_cost": float(row.get("system_cost_index", 0.0)),\n'
        '            "system_cost_bonuses": float(row.get("system_cost_bonuses", 0.0)),\n'
        '        }\n',
        "industry fee breakdown",
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

    # Replace the exact fee calculation with a fully-loaded model. The BPC contract price remains
    # a cost as well; manufacturing_job_cost includes SCC and is subtracted exactly once.
    source = replace_once(
        source,
        '            job_cost=0.0; job_hours=0.0; ok=True\n'
        '            for j in p["jobs"]:\n'
        '                q=industry_quote(j["bp_tid"],j["product_tid"],j["runs"],j["me"],j["te"],fac["system_id"])\n'
        '                if not q: ok=False; break\n'
        '                job_cost += q["job_cost"] * j["copies"]\n'
        '                job_hours += q["time_hours"] * j["copies"]\n'
        '            if not ok: continue\n'
        '            sales_tax = p["gross_revenue"]*tax_rate\n'
        '            haul_cost = p["haul_m3"]*HIGHSEC_HAUL_ISK_PER_M3\n'
        '            net = p["gross_revenue"] - p["contract_price"] - p["material_cost"] - job_cost - sales_tax - haul_cost\n'
        '            base = p["contract_price"] + p["material_cost"] + job_cost + haul_cost\n'
        '            roi = net/base if base else 0\n'
        '            cand={"fac":fac,"job_cost":job_cost,"job_hours":job_hours,"sales_tax":sales_tax,"haul_cost":haul_cost,"net":net,"roi":roi}\n',
        '            job_cost=0.0; job_hours=0.0; scc_cost=0.0; facility_tax_cost=0.0; sci_cost=0.0; ok=True\n'
        '            for j in p["jobs"]:\n'
        '                q=industry_quote(j["bp_tid"],j["product_tid"],j["runs"],j["me"],j["te"],fac["system_id"])\n'
        '                if not q: ok=False; break\n'
        '                copies=j["copies"]\n'
        '                job_cost += q["job_cost"] * copies\n'
        '                job_hours += q["time_hours"] * copies\n'
        '                scc_cost += q.get("scc_surcharge",0.0) * copies\n'
        '                facility_tax_cost += q.get("facility_tax_cost",0.0) * copies\n'
        '                sci_cost += (q.get("system_cost_index_cost",0.0) + q.get("system_cost_bonuses",0.0)) * copies\n'
        '            if not ok: continue\n'
        '            sales_tax = p["gross_revenue"]*tax_rate\n'
        '            broker_fee = p["gross_revenue"]*MARKET_BROKER_FEE_RATE\n'
        '            relist_cost = p["gross_revenue"]*RELIST_RESERVE_RATE\n'
        '            haul_cost = p["haul_m3"]*HIGHSEC_HAUL_ISK_PER_M3\n'
        '            net = p["gross_revenue"] - p["contract_price"] - p["material_cost"] - job_cost - broker_fee - sales_tax - relist_cost - haul_cost\n'
        '            base = p["contract_price"] + p["material_cost"] + job_cost + broker_fee + relist_cost + haul_cost\n'
        '            roi = net/base if base else 0\n'
        '            cand={"fac":fac,"job_cost":job_cost,"job_hours":job_hours,"scc_cost":scc_cost,"facility_tax_cost":facility_tax_cost,"sci_cost":sci_cost,"broker_fee":broker_fee,"sales_tax":sales_tax,"relist_cost":relist_cost,"haul_cost":haul_cost,"net":net,"roi":roi}\n',
        "fully loaded exact fees",
    )

    # Break-even buy depth must also cover all market percentage costs.
    source = replace_once(
        source,
        '            break_even_bid=fixed/(int(output_qty)*(1-tax_rate))\n',
        '            sale_keep_rate=1-tax_rate-MARKET_BROKER_FEE_RATE-RELIST_RESERVE_RATE\n'
        '            break_even_bid=fixed/(int(output_qty)*sale_keep_rate) if sale_keep_rate>0 else np.inf\n',
        "fully loaded break-even bid",
    )

    # Publish every cost component for auditability. SCC/facility/SCI are a breakdown of job_cost,
    # not extra deductions beyond manufacturing_job_cost.
    source = replace_once(
        source,
        '            "contract_price":p["contract_price"],"material_cost_jita_depth":p["material_cost"],"manufacturing_job_cost":best["job_cost"],\n'
        '            "sales_tax":best["sales_tax"],"configured_haul_cost":best["haul_cost"],"gross_revenue":p["gross_revenue"],"net_profit":best["net"],"net_roi":best["roi"],\n',
        '            "contract_price":p["contract_price"],"material_cost_jita_depth":p["material_cost"],"manufacturing_job_cost":best["job_cost"],\n'
        '            "industry_scc_surcharge":best["scc_cost"],"industry_facility_tax":best["facility_tax_cost"],"industry_sci_component":best["sci_cost"],\n'
        '            "market_broker_fee":best["broker_fee"],"sales_tax":best["sales_tax"],"relist_cost_reserve":best["relist_cost"],"configured_haul_cost":best["haul_cost"],\n'
        '            "gross_revenue":p["gross_revenue"],"net_profit":best["net"],"net_roi":best["roi"],\n',
        "fee output columns",
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

    # Record the cost model in meta for later diagnostics.
    source = replace_once(
        source,
        '        "accounting_level":ACCOUNTING_LEVEL,"transaction_tax_rate":tax_rate,"factory_candidates":factories,\n',
        '        "accounting_level":ACCOUNTING_LEVEL,"transaction_tax_rate":tax_rate,"market_broker_fee_rate":MARKET_BROKER_FEE_RATE,\n'
        '        "expected_relists":EXPECTED_RELISTS,"relist_reserve_rate":RELIST_RESERVE_RATE,"haul_isk_per_m3":HIGHSEC_HAUL_ISK_PER_M3,"factory_candidates":factories,\n',
        "fee model meta",
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
        "Fast fully-loaded scanner: gross>=30M, rough ROI>=5%, single product, "
        "<=2 days 30d volume, top150, 2 factories; final profit includes BPC, materials, "
        "industry job cost (SCI+facility+SCC), broker fee, sales tax, relist reserve and configured haul."
    )
    exec(
        compile(tree, "scanner_fast.py", "exec"),
        {"__name__": "__main__", "__safe_int": safe_int},
    )


if __name__ == "__main__":
    main()
