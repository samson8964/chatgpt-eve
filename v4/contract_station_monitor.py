"""Per-origin contract research census for the current V4 market/contract run.

Counts are from public item-exchange contract snapshots, not private corp
contracts. "model_candidates" are shadow price-model candidates, not live
executable contracts and not necessarily the final EVE mail top ten.
"""
from __future__ import annotations

from collections import Counter

from v4.structure_registry import STRUCTURES

NPC_HUBS = (
    ("amarr", 60008494, "艾玛 VIII", "PUBLIC_NPC"),
    ("dodixie", 60011866, "多迪谢 IX", "PUBLIC_NPC"),
)


def station_contract_summary(source_locations, proofs, *, structures=None) -> dict:
    """Summarize already-scoped cash contracts and audited proof outcomes.

    Uses the exact active five-station registry; counts do not grant
    additional structure or NPC authorization and do not scan again.
    """
    structures = STRUCTURES if structures is None else structures
    targets = [
        (lane, int(structure_id), lane, "AUTHORIZED_STRUCTURE")
        for lane, (structure_id, profile) in structures.items()
    ] + list(NPC_HUBS)
    ids = [ident for _, ident, _, _ in targets]
    if len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_TARGET_CONTRACT_STATION_ID")
    counts = Counter(int(x) for x in source_locations if x is not None)
    audited = Counter()
    model = Counter()
    for proof in proofs:
        if not isinstance(proof, dict) or proof.get("kind") != "contract":
            continue
        location = proof.get("source_location")
        if isinstance(location, bool) or not isinstance(location, int):
            continue
        audited[location] += 1
        if proof.get("model_candidate") is True:
            model[location] += 1
    return {
        "basis": "PUBLIC_ITEM_EXCHANGE_SNAPSHOT_AND_SHADOW_PROOFS",
        "private_contracts_not_in_public_archive": "NOT_VISIBLE",
        "model_candidates_are_not_live_verified": True,
        "stations": {
            lane: {
                "location_id": ident,
                "source_type": source_type,
                "scoped_cash_contracts": counts[ident],
                "audited_contract_proofs": audited[ident],
                "shadow_model_candidates": model[ident],
            }
            for lane, ident, label, source_type in targets
        },
    }
