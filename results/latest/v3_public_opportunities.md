# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-13T01:01:53.211Z
- Market snapshot: 2026-10-13T00:48:47.610Z
- Candidate universe: 25094; deep validation pool: 232; feasible: 141
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 3
- RESEARCH: 129
- FORMAL MAIL: 1

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50730`
- eligible_contracts: `44494`
- market_executable_contracts: `25094`
- snapshot_candidates: `25094`
- candidate_pool: `612`
- location_executable: `232`
- feasible: `141`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `3`
- research_watch: `129`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19176`
- MARKET_INELIGIBLE_SINGLETON: `6466`
- UNSAFE_OR_UNVERIFIED_LOCATION: `380`
- HIGHSEC_RESTRICTED_CAPITAL: `85`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- SKIN_DOMINANT: `6`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
- LIST_DATA_INCOMPLETE: `5`
