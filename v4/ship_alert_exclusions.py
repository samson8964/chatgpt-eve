"""Mandatory V4 mail-only capital ship and freighter exclusion.

Applies to EVERY research-mail lead category before sorting and each 10-lead
display cap. Keeps raw archived scan proofs unchanged for audit.

Ship class inventory group IDs are from EVE Ref's category=Ship and CCP ESI
type group metadata, not English/Chinese substring matching.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from v4.catalog import Catalog, DEFAULT_CACHE
from v4.blueprint_recipes import RECIPE_CACHE, load as load_recipes

# Capital hulls, including newer T2 Command Carriers and Lancer Dreads.
CAPITAL_GROUPS = frozenset({
    30,    # Titan
    485,   # Dreadnought
    547,   # Carrier
    659,   # Supercarrier
    883,   # Capital Industrial Ship (Rorqual)
    1538,  # Force Auxiliary
    4594,  # Lancer Dreadnought
    5120,  # Command Carrier (2026)
})
FREIGHTER_GROUPS = frozenset({
    513,   # Freighter incl. Bowhead / Avalanche
    902,   # Jump Freighter
})
BLOCKED_SHIP_GROUPS = CAPITAL_GROUPS | FREIGHTER_GROUPS
POLICY_NAME = "NO_CAPITAL_OR_FREIGHTER_HULLS_OR_HULL_BLUEPRINTS_V1"


@dataclass
class ExclusionPolicy:
    blocked_hull_types: frozenset[int]
    blocked_blueprint_types: frozenset[int]
    unclassified_blueprint_types: frozenset[int]
    catalog_sha256: str | None
    manufacturing_recipes_installed: bool

    def blocks_market(self, type_id) -> bool:
        try:
            return int(type_id) in self.blocked_hull_types
        except (TypeError,ValueError,OverflowError):
            return True  # Fail closed on malformed identifiers.

    def blocks_contract(self, included_items: dict) -> bool:
        """Any excluded hull or matching BPO/BPC suppresses the whole bundle.

        Even if the excluded hull wasn't credited in the ordinary subset
        liquidation and is technically a zero-value 'bonus'.
        """
        if not isinstance(included_items,dict) or not included_items:
            return True
        try:
            types={int(t) for t in included_items}
        except (TypeError,ValueError,OverflowError):
            return True
        return bool(types & (self.blocked_hull_types | self.blocked_blueprint_types |
                             self.unclassified_blueprint_types))

    def blocks_blueprint(self, blueprint_type, output_type) -> bool:
        try:
            bp=int(blueprint_type)
            product=int(output_type)
        except (TypeError,ValueError,OverflowError):
            return True
        return (product in self.blocked_hull_types or
                bp in self.blocked_blueprint_types or
                bp in self.unclassified_blueprint_types)


def build_policy(catalog: Catalog, recipe_data: dict | None) -> ExclusionPolicy:
    blocked_hulls=frozenset(
        int(t) for t in catalog.items
        if catalog.classification(t) == "regular" and
           catalog.group_id(t) in BLOCKED_SHIP_GROUPS
    )
    if not blocked_hulls:
        raise RuntimeError("SHIP_EXCLUSION_NO_HULL_GROUPS_IN_CATALOG")
    blocked_blueprints=set()
    unknown_blueprints=set()
    recipes=(recipe_data or {}).get("manufacturing_recipes") or {}
    for type_id,group in catalog.items.items():
        if catalog.classification(type_id)!="blueprint_type":
            continue
        recipe=recipes.get(str(type_id))
        if not isinstance(recipe,dict):
            # This blueprint has no verified manufacturing product mapping;
            # don't infer that it is or isn't an excluded capital blueprint.
            # Fail closed for mixed ordinary contracts in this rare case.
            unknown_blueprints.add(int(type_id))
            continue
        products=recipe.get("products")
        if not isinstance(products,dict) or not products:
            unknown_blueprints.add(int(type_id))
            continue
        try:
            out={int(x) for x in products}
        except (TypeError,ValueError,OverflowError):
            unknown_blueprints.add(int(type_id))
            continue
        if out & blocked_hulls:
            blocked_blueprints.add(int(type_id))
    return ExclusionPolicy(
        blocked_hull_types=blocked_hulls,
        blocked_blueprint_types=frozenset(blocked_blueprints),
        unclassified_blueprint_types=frozenset(unknown_blueprints),
        catalog_sha256=catalog.meta.get("sha256"),
        manufacturing_recipes_installed=bool(recipe_data),
    )


def load_policy_for_run(report: dict, *, repo: Path | None=None) -> ExclusionPolicy | None:
    """Actual production runs MUST match their item-group catalog.

    Synthetic CI fixtures predating item-catalog integration have no
    catalog_meta and remain testable without downloading/installing SDE.
    All real v4.deep_scan runs include catalog_meta.
    """
    scan_meta=report.get("catalog_meta")
    if not isinstance(scan_meta,dict):
        return None
    repo=repo or Path(__file__).resolve().parent.parent
    path=repo/DEFAULT_CACHE
    if not path.is_file():
        raise RuntimeError("SHIP_EXCLUSION_REFERENCE_MISSING")
    catalog=Catalog.load(path)
    source_sha=scan_meta.get("sha256")
    if source_sha and catalog.meta.get("sha256") != source_sha:
        raise RuntimeError("SHIP_EXCLUSION_REFERENCE_VERSION_MISMATCH")
    try:
        recipes=load_recipes(repo/RECIPE_CACHE)
    except (OSError,ValueError,TypeError,RuntimeError) as exc:
        raise RuntimeError("SHIP_EXCLUSION_BLUEPRINT_REFERENCE_INVALID") from exc
    return build_policy(catalog,recipes)
