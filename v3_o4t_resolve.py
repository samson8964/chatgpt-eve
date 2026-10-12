"""Resolve exactly the user's O4T-Z5 Dracarys. Prime building via LadyBaBa DC ESI.

No guesses from nearby structures, contract mentions, or a successful OAuth alone.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import requests

SYSTEM_ID = 30004691
EXPECTED_NAME_PARTS = ("dracarys", "prime")
RESULT = Path("results/latest/v3_dc_o4t_access.json")


def select_prime_structure(payload: dict) -> dict:
    if payload.get("ok") is not True:
        raise RuntimeError("DC structure search did not return an OK response")
    if int(payload.get("target_system_id") or 0) != SYSTEM_ID:
        raise RuntimeError("O4T target system mismatch; refusing to scan another system")
    rows = payload.get("structures") or []
    matches = [
        r for r in rows
        if int(r.get("solar_system_id") or 0) == SYSTEM_ID
        and all(part in str(r.get("name") or "").casefold() for part in EXPECTED_NAME_PARTS)
        and int(r.get("structure_id") or 0) >= 1_000_000_000_000
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one market-accessible O4T Dracarys Prime, found {len(matches)}. "
            f"discovery={payload.get('discovery_status', 'unknown')}, "
            f"candidates={payload.get('candidate_count', '?')}, "
            f"checked_this_run={payload.get('checked_this_run', '?')}, "
            f"cursor={payload.get('candidate_cursor', '?')}, "
            f"next_public_page={payload.get('next_public_page', '?')}, "
            f"metadata_denied={payload.get('metadata_denied', '?')}, "
            f"market_denied={payload.get('market_denied', '?')}. "
            "Refusing to select a different player structure."
        )
    chosen = matches[0]
    return {
        "structure_id": int(chosen["structure_id"]),
        "name": str(chosen["name"]).replace("\n", " "),
        "system_id": SYSTEM_ID,
        "market_pages": int(chosen.get("market_pages") or 0),
        "page1_orders": int(chosen.get("page1_orders") or 0),
    }


def main() -> None:
    base = (os.getenv("EVE_MARKET_WORKER_URL") or "").rstrip("/")
    key = os.getenv("EVE_MARKET_API_KEY") or ""
    if not base or not key:
        raise RuntimeError("Missing EVE_MARKET_WORKER_URL / EVE_MARKET_API_KEY")
    resp = requests.get(
        base + "/api/structure-search",
        params={"q": "O4T-Z5", "auth_profile": "dc"},
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        timeout=90,
    )
    if resp.status_code != 200:
        try:
            error = resp.json()
            detail = f"{error.get('error', 'unknown')}: {str(error.get('detail', ''))[:250]}"
        except Exception:
            detail = resp.text[:250]
        raise RuntimeError(
            f"DC structure lookup returned HTTP {resp.status_code}: {detail}. "
            "Investigate Worker discovery diagnostics before reauthorizing /auth-dc."
        )
    payload = resp.json()
    print(
        "O4T discovery progress:",
        {
            k: payload.get(k) for k in (
                "discovery_status", "candidate_count", "checked_this_run",
                "candidate_cursor", "next_public_page", "public_pages",
                "search_status", "public_contracts_status",
                "metadata_denied", "market_denied", "esi_requests",
            )
        },
    )
    selected = select_prime_structure(payload)
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps({"ok": True, **selected}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output = os.getenv("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"structure_id={selected['structure_id']}\n")
            stream.write(f"structure_name={selected['name']}\n")
    print("Verified O4T Dracarys Prime:", selected)


if __name__ == "__main__":
    main()
