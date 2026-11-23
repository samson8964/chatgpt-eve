# V4 ordinary contract credited subset + independent blueprint manufacture research

## Policy (user approved)

Ordinary item-exchange contracts: pay **100% of the displayed contract ISK price**. Credit only the selected subset of non-blueprint item types, and at most the actual available Jita 4-4 station BUY order quantity for each credited type. Any noncredited item has ISK resale value **zero**. Uncredited leftovers can be left at source and therefore are not included in Jita shipping volume. The credited goods' actual volume is included in source-to-Jita shipping estimates. Never count requested/bartered items as free.

Research candidates require net >= 50,000,000 ISK and net/(contract price + credited cargo freight) **strictly greater than 10%**. The normal sale tax is already subtracted; stress after removal of best Jita BUY is displayed if known but is not a rejection condition for ordinary contracts. Preserve the energy laser crystal exclusion when >=50% of credited cash liquidation comes from energy laser crystals; unknown group types are not credited and never contribute to the denominator.

All contracts remain snapshot RESEARCH/WATCH, NOT live-verified executable trading alerts. Each independently verified item can fund the full contract price without requiring liquidation of other items.

## Why previous 'classification unverified or blueprint' blocked ~26k contracts

The V4 legacy contract_proof required catalog.classification(type_id)=='regular' **for every included item**. EVE Ref reference type IDs not indexed return 'unknown'; even one blueprint-type item caused the entire contract to be rejected. This did NOT mean all ~26k contracts had broken metadata; blueprint-type items were grouped into the same reason. The new ordinary scan ignores (zero credits) blueprint, unknown and unpriced items rather than rejecting the entire contract. The dedicated blueprint pathway uses actual contract BPO/BPC instance metadata and manufacturing recipes. The report records ignored blueprint, unknown and no-bid item-type counts; original items remain in saved proofs.

## Blueprint manufacturing: third independent 10-slot email category

BluePrint recipes come from EVE Ref **blueprints.json** in reference-data-latest.tar.xz. One-time setup is explicit; the hourly scanner only reads the cached manufacturing recipe file. With no installed recipe file, markets and ordinary contracts continue; blueprint status reports NOT_INSTALLED, not invented opportunities.

    Set-Location (Join-Path $HOME 'EVE-V4-Code')
    git pull --ff-only
    & .\.venv\Scripts\python.exe -m v4.blueprint_recipes --install
    & .\.venv\Scripts\python.exe -m v4.blueprint_recipes --status

After the next completed hourly scan inspect the newest deep_shadow.json fields: contract_partial_credited_proofs, contract_partial_ignored_blueprint_item_types, contract_partial_ignored_unclassified_item_types, contract_partial_ignored_no_jita_buy_item_types, blueprint_manufacturing_recipe_status and blueprint_manufacturing_candidates. The email has 10 each for market, ordinary contract and blueprint manufacture, not 10 total.

Manufacturing estimate: Jita 4-4 BUY order depth for final products, Jita 4-4 SELL depth for every required material, material quantities adjusted to per-contract blueprint material efficiency (ME) and assumed production runs, full contract price, blueprint freight, sales tax and a **disclosed 20% of material cost manufacturing-fee reserve**. BPC is limited by licensed production runs (at most 10 per scenario), BPO research uses at most ten runs without assigning infinite value. The model does NOT claim a verified live facility quote, cost index, SCC fees, training skills, build time, available industry slots or access. Every blueprint lead is labelled estimated/non-actionable and is NOT equivalent to a verified execution-profit calculation. Precise job cost requires ESI industry system indices, adjusted-price-based estimated item value, facility tax/rig/skill parameters and an explicitly selected manufacturing station in a subsequent upgrade.

Risk rules: If no audited recipe, no verified BPO/BPC flag/runs/ME, no complete needed Jita material SELL order depth, or no complete Jita product BUY depth, do not report a blueprint manufacturing-profit candidate. Never value a BPC at a BPO resale price. Recipe installation failure or missing cache must not interrupt normal market/contract scanning.

CCP official sources:
- https://support.eveonline.com/hc/en-us/articles/203210292-Manufacturing
- https://support.eveonline.com/hc/en-us/articles/203269951-Blueprints
- https://support.eveonline.com/hc/en-us/articles/203210542-Material-Efficiency-Research
- https://support.eveonline.com/hc/en-us/articles/203210602-Copying
- https://docs.everef.net/datasets/reference-data.html