"""Offline counterfactual audit of archived contract and BPC opportunities.

Never calls the scanner, ESI, discovery/mail builders, or SQLite; never writes
production files. Alternative thresholds and combined valuations are research,
not mail eligibility or live executable quotes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from v4.contract_blueprint_diagnostics import latest_folders
from v4.contract_partial import CONTRACT_REFERENCE_BASIS, CONTRACT_VALUATION_BASIS
from v4.ship_alert_exclusions import load_policy_for_run

FEE_BASIS = "ESI_ADJUSTED_PRICES_SYSTEM_COST_INDEX_JITA_NPC_REFERENCE_NOT_JOB_QUOTE"
BP_BASIS = "JITA_TOP5_BPC_MANUFACTURE_30PCT_BUNDLE_ESTIMATE"
FLOOR, ROI = 50_000_000, .10
JITA = 60003760
SCENARIOS = ((50_000_000,.10),(20_000_000,.10),(50_000_000,.05),(20_000_000,.05))


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def number(value):
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError, OverflowError):
        return None


def economics(row):
    net, roi, cost = (number(row.get(k)) for k in ("net_profit","roi","cost"))
    return (net,roi,cost) if None not in (net,roi,cost) and cost > 0 else None


def passed(row, floor=FLOOR, roi=ROI):
    e = economics(row)
    return e is not None and e[0] >= floor and e[1] > roi


def ordinary_valid(row, exclusion):
    share = number(row.get("energy_crystal_value_share"))
    price = number(row.get("contract_price"))
    items = row.get("included_items")
    return (economics(row) is not None and price is not None and price > 0
            and share is not None and 0 <= share < .5
            and row.get("valuation_basis") == CONTRACT_VALUATION_BASIS
            and row.get("valuation_location_id") == JITA
            and row.get("destination_location") == JITA
            and row.get("reason") in (
                "LIVE_ORDER_AND_CONTRACT_NOT_REVALIDATED","BELOW_GATE_OR_STRESS")
            and row.get("status") != "MAIL"
            and isinstance(items, dict) and bool(items)
            and not exclusion.blocks_contract(items))


def blueprint_valid(row, exclusion):
    risk = number(row.get("risk_score"))
    details = row.get("bundle_selected_details")
    price = number(row.get("contract_price_isk"))
    return (economics(row) is not None and price is not None and price > 0
            and row.get("status") == "WATCH"
            and row.get("blueprint_kind") == "BPC"
            and row.get("valuation_basis") == BP_BASIS
            and row.get("facility_fee_status") == FEE_BASIS
            and row.get("manufacturing_fee_snapshot_verified") is True
            and row.get("jita_material_top5_prices_observed") is True
            and row.get("jita_product_top5_prices_observed") is True
            and risk is not None and 0 <= risk <= 100
            and isinstance(details,list) and bool(details)
            and all(isinstance(x,dict) and not exclusion.blocks_blueprint(
                x.get("blueprint_type_id"),x.get("product_type_id"))
                    for x in details))


def combine(ordinary, blueprint):
    """Same contract, same price, disjoint acquired assets; charge price once.

    Uses each archived leg's net and cost, preserving both hauling charges,
    original manufacturing costs and taxes. It does NOT combine a BPC resale
    value with its manufacturing value or pretend indicative quotes are fills.
    """
    if ordinary.get("contract_id") != blueprint.get("contract_id"):
        return None
    if ordinary.get("source_location") != blueprint.get("source_location"):
        return None
    p = number(ordinary.get("contract_price"))
    q = number(blueprint.get("contract_price_isk"))
    a, b = economics(ordinary), economics(blueprint)
    if p is None or q is None or p <= 0 or p != q or a is None or b is None:
        return None
    try:
        included = {int(t) for t in ordinary["included_items"]}
        credited = {int(t) for t in ordinary["credited_items"]}
        selected = {int(x["blueprint_type_id"])
                    for x in blueprint["bundle_selected_details"]}
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if not credited or not selected or credited & selected:
        return None
    if not (credited | selected) <= included:
        return None
    if a[2] < p or b[2] < p or a[0]+p <= 0 or b[0]+p <= 0:
        return None
    net = a[0]+b[0]+p
    cost = a[2]+b[2]-p
    if not math.isfinite(net) or not math.isfinite(cost) or cost <= 0:
        return None
    return {"contract_id":ordinary["contract_id"],"contract_price":p,
            "net_profit":net,"cost":cost,"roi":net/cost,
            "ordinary_net":a[0],"bpc_net":b[0],
            "ordinary_history_reference_share":ordinary.get(
                "contract_history_reference_share"),
            "ordinary_liquidity_flags":ordinary.get("contract_liquidity_risk_flags") or [],
            "bpc_risk_flags":blueprint.get("risk_flags") or [],
            "research_only":True,"live_verified":False}


def analyze_rows(rows, exclusion):
    ordinary, bp = {}, {}
    counts, reasons, ignored = Counter(), Counter(), Counter()
    for row in rows:
        kind = row.get("kind")
        if kind not in ("contract","blueprint_manufacturing"):
            continue
        cid = row.get("contract_id")
        if not isinstance(cid,int) or isinstance(cid,bool) or cid <= 0:
            counts["invalid_contract_id"] += 1
            continue
        target = ordinary if kind=="contract" else bp
        if cid in target:
            raise ValueError("DUPLICATE_CONTRACT_PROOF:"+str(cid))
        target[cid]=row
        reasons[kind+":"+str(row.get("reason") or "UNKNOWN")] += 1
        if kind=="contract":
            for key in ("ignored_no_reference_types","ignored_unclassified_types",
                        "ignored_blueprint_types"):
                ignored[key] += int(row.get(key) or 0)

    valid_o = {cid:r for cid,r in ordinary.items() if ordinary_valid(r,exclusion)}
    valid_b = {cid:r for cid,r in bp.items() if blueprint_valid(r,exclusion)}
    eligible_o = {cid for cid,r in valid_o.items() if passed(r)}
    eligible_b = {cid for cid,r in valid_b.items()
                  if passed(r) and r.get("model_candidate") is True}

    bpc_contracts = {cid for cid,r in ordinary.items()
                     if (r.get("contract_blueprint_evidence") or {}).get("BPC",0)>0}
    bpo_contracts = {cid for cid,r in ordinary.items()
                     if (r.get("contract_blueprint_evidence") or {}).get("BPO",0)>0}
    both = sorted(set(valid_o)&set(valid_b))
    combos = [c for cid in both if (c:=combine(valid_o[cid],valid_b[cid])) is not None]
    rescued = sorted((c for c in combos if passed(c)
                      and c["contract_id"] not in eligible_o|eligible_b),
                     key=lambda x:-x["net_profit"])
    sensitivity = {}
    for floor,roi in SCENARIOS:
        label=f"net_{floor//1_000_000}m_roi_gt_{round(roi*100)}pct"
        sensitivity[label]={"ordinary":sum(passed(r,floor,roi) for r in valid_o.values()),
                            "bpc":sum(passed(r,floor,roi) for r in valid_b.values()),
                            "combined_additional":sum(passed(r,floor,roi)
                                and not passed(valid_o[r["contract_id"]],floor,roi)
                                and not passed(valid_b[r["contract_id"]],floor,roi)
                                for r in combos)}
    missing_bpc=bpc_contracts-set(bp)
    for cid in missing_bpc:
        if cid not in ordinary: raise AssertionError("MISSING_ORDINARY_PROOF")
    return {
        "contract_proofs":len(ordinary),
        "contract_numeric":sum(economics(r) is not None for r in ordinary.values()),
        "contract_numeric_gate":sum(passed(r) for r in ordinary.values()),
        "ordinary_non_economic_gates_pass":len(valid_o),
        "ordinary_current_candidates_before_top10":len(eligible_o),
        "ordinary_crystal_majority_numeric_gate":sum(passed(r) and
            (number(r.get("energy_crystal_value_share")) or 0)>=.5
            for r in ordinary.values()),
        "booster_excluded_contracts":sum(r.get("reason")=="BOOSTER_BLUEPRINT_CONTRACT_EXCLUDED"
                                         for r in ordinary.values()),
        "contracts_with_bpc_evidence":len(bpc_contracts),
        "contracts_with_bpo_evidence":len(bpo_contracts),
        "bpo_only_contracts":len(bpo_contracts-bpc_contracts),
        "bpc_contracts_without_manufacturing_proof":len(missing_bpc),
        "manufacturing_proofs":len(bp),
        "manufacturing_numeric_gate":sum(passed(r) for r in bp.values()),
        "manufacturing_verified_non_economic_gates":len(valid_b),
        "manufacturing_current_candidates_before_top10":len(eligible_b),
        "manufacturing_missing_verified_fee":sum(
            r.get("manufacturing_fee_snapshot_verified") is not True for r in bp.values()),
        "reason_counts":dict(reasons.most_common(16)),
        "ignored_item_type_occurrences":dict(ignored),
        "mixed_with_two_compatible_proofs":len(combos),
        "mixed_additional_candidates":len(rescued),
        "top_mixed_research_examples":rescued[:5],
        "threshold_sensitivity_research_only":sensitivity,
        "_ordinary_ids":sorted(eligible_o),"_bpc_ids":sorted(eligible_b),
        "_mixed_ids":sorted(x["contract_id"] for x in rescued),
        "_missing_bpc_ids":sorted(missing_bpc),
    }


def raw_drilldown(folder, deep, census, ids):
    """Trace missing BPC proofs using saved raw market/contract archives.
    No historical ESI fee snapshot is reconstructed from today's values.
    """
    if not ids:
        return {"status":"NO_MISSING_BPC_PROOFS","contract_count":0}
    from v4 import catalog as catalog_module
    from v4.catalog import Catalog, DEFAULT_CACHE, blueprint_instance_kind
    from v4.blueprint_recipes import load, RECIPE_CACHE
    from v4.sources import market_dataframe, contract_dataframes
    from v4.deep_scan import to_orders
    repo = Path(catalog_module.__file__).resolve().parent.parent
    market_file=folder/"source"/"market_orders.csv.bz2"
    contract_file=folder/"source"/"public_contracts.tar.bz2"
    for name,path in (("market_orders",market_file),("public_contracts",contract_file)):
        expected=(census.get("sources") or {}).get(name,{}).get("sha256")
        if not path.is_file() or path.is_symlink() or not expected:
            return {"status":"RAW_ARCHIVE_OR_HASH_MISSING","source":name}
        with path.open("rb") as f:
            if hashlib.file_digest(f,"sha256").hexdigest()!=expected:
                return {"status":"RAW_ARCHIVE_HASH_MISMATCH","source":name}
    catalog=Catalog.load(repo/DEFAULT_CACHE)
    if catalog.meta.get("sha256") != (deep.get("catalog_meta") or {}).get("sha256"):
        return {"status":"CATALOG_MISMATCH"}
    recipe_data=load(repo/RECIPE_CACHE) or {}
    recipes=recipe_data.get("manufacturing_recipes") or {}
    if len(recipes)!=deep.get("blueprint_manufacturing_recipe_count"):
        return {"status":"RECIPE_COUNT_DIFFERS_FROM_SCAN"}
    _,items=contract_dataframes(contract_file)
    subset=items[items["contract_id"].isin(ids)]
    flags=subset["is_included"].astype(str).str.lower().isin(["true","1","t"])
    subset=subset.loc[flags]
    frame=market_dataframe(market_file)
    station=frame[frame["location_id"]==JITA]
    orders,_=to_orders(station.to_dict("records"),source="PUBLIC")
    bids={o.type_id for o in orders if o.buy}
    asks={o.type_id for o in orders if not o.buy}
    counters=Counter()
    per_contract={}
    seen=set()
    for item in subset.to_dict("records"):
        cid=int(item["contract_id"])
        typ=int(item["type_id"])
        if catalog.classification(typ)!="blueprint_type":
            continue
        if blueprint_instance_kind(item.get("is_blueprint_copy"),item.get("runs"))!="BPC":
            continue
        seen.add(cid)
        me=number(item.get("material_efficiency"))
        runs=number(item.get("runs"))
        qty=number(item.get("quantity"))
        recipe=recipes.get(str(typ))
        if (me is None or not 0<=me<=10 or runs is None or runs<=0
                or qty is None or qty<=0 or runs*qty>10_000_000):
            reason="BPC_METADATA_INVALID"
        elif not isinstance(recipe,dict) or not recipe.get("materials") or len(recipe.get("products") or {})!=1:
            reason="MANUFACTURING_RECIPE_MISSING_OR_UNSUPPORTED"
        elif not all(int(t) in bids for t in recipe["products"]):
            reason="PRODUCT_NO_JITA_BUY_PRICE"
        elif not all(int(t) in asks for t in recipe["materials"]):
            reason="MATERIAL_NO_JITA_SELL_PRICE"
        else:
            reason="QUOTES_PRESENT_OTHER_CAUSE_UNRESOLVED"
        counters[reason]+=1
        per_contract.setdefault(cid,set()).add(reason)
    by_contract=Counter(k for reasons in per_contract.values() for k in reasons)
    return {"status":"RAW_HASH_VERIFIED_QUOTE_AVAILABILITY_AUDIT",
            "missing_bpc_contracts":len(ids),"raw_bpc_contracts_seen":len(seen),
            "missing_bpc_contracts_not_reconstructed":len(set(ids)-seen),
            "bpc_entry_first_blocker_counts":dict(counters),
            "contract_blocker_counts_nonexclusive":dict(by_contract),
            "historical_fee_source":deep.get("blueprint_manufacturing_fee_source"),
            "historical_fee_error":deep.get("blueprint_manufacturing_fee_source_error"),
            "limits":"Current recipe cache count matches, not historical recipe hash. Quotes-present residual may be negative contribution, fees, route, or other metadata; no exact historic fee replay."}


def audit(root, last=12, raw=True):
    outputs=[]
    unique={k:set() for k in ("ordinary","bpc","mixed")}
    excluded_runs=[]
    latest_raw=None
    for folder in latest_folders(root,last):
        deep=_json(folder/"deep_shadow.json")
        census=_json(folder/"full_market_report.json")
        manifest=_json(folder/"manifest.json")
        if deep.get("contract_partial_valuation_basis")!=CONTRACT_REFERENCE_BASIS:
            excluded_runs.append({"run":folder.name,"reason":"OLDER_VALUATION_VERSION"})
            continue
        try:
            exclusion=load_policy_for_run(deep)
            if exclusion is None:
                raise ValueError("NO_VERIFIED_EXCLUSION_POLICY")
        except (OSError,ValueError,RuntimeError) as exc:
            excluded_runs.append({"run":folder.name,"reason":str(exc)})
            continue
        with (folder/"all_proofs.jsonl").open(encoding="utf-8") as f:
            report=analyze_rows((json.loads(line) for line in f if line.strip()),exclusion)
        report.update(run=folder.name,
                      public_contract_rows=(census.get("contracts") or {}).get("contract_rows_total"),
                      approved_cash_contracts=deep.get("contract_approved_locations_examined"),
                      requested_item_excluded=deep.get("contract_requested_items_excluded"),
                      coverage_gate=manifest.get("coverage_gate"),
                      contract_source_timestamp=(census.get("sources") or {}).get(
                          "public_contracts",{}).get("last_modified"),
                      fee_source=deep.get("blueprint_manufacturing_fee_source"),
                      fee_error=deep.get("blueprint_manufacturing_fee_source_error"))
        for kind in unique:
            unique[kind].update(report.pop("_"+kind+"_ids"))
        missing=report.pop("_missing_bpc_ids")
        if latest_raw is None and raw:
            try:
                latest_raw={"run":folder.name,**raw_drilldown(folder,deep,census,missing)}
            except (OSError,ValueError,KeyError,TypeError,RuntimeError) as exc:
                latest_raw={"run":folder.name,"status":"RAW_AUDIT_UNAVAILABLE",
                            "reason":type(exc).__name__+":"+str(exc)[:160]}
        outputs.append(report)
    return {"status":"READ_ONLY_CONTRACT_OPPORTUNITY_LOSS_AUDIT",
            "runs_analyzed":len(outputs),"runs_skipped":excluded_runs,
            "distinct_candidate_contract_ids_across_runs":{k:len(v) for k,v in unique.items()},
            "latest_raw_blueprint_drilldown":latest_raw,"runs":outputs,
            "research_only":True,"files_modified":False,
            "mail_sent":False,"production_rules_changed":False,
            "limitations":["Current model candidates before cap, not confirmed delivered mail.",
                           "Repeated contracts deduplicated in cross-run totals.",
                           "Mixed audit only combines existing same-snapshot disjoint proofs; cannot value unpriced items or BPO resale.",
                           "Counterfactuals do not alter user-approved thresholds or exclusions.",
                           "No live availability, liquidation or manufacturing capacity asserted."]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root",type=Path,default=Path.home()/"EVE-V4-Data")
    parser.add_argument("--last",type=int,default=12)
    parser.add_argument("--skip-raw",action="store_true")
    args=parser.parse_args()
    if not 1<=args.last<=20:
        parser.error("--last must be 1..20")
    print(json.dumps(audit(args.data_root,args.last,not args.skip_raw),
                     ensure_ascii=False,indent=2,allow_nan=False))


if __name__=="__main__":
    main()
