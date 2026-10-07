# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T17:31:24.394Z
- Market snapshot: 2026-10-07T17:18:33.742Z
- Candidate universe: 24401; deep validation pool: 252; feasible: 191
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 152
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

- raw_contracts: `49624`
- eligible_contracts: `43122`
- market_executable_contracts: `24401`
- snapshot_candidates: `24401`
- candidate_pool: `605`
- location_executable: `252`
- feasible: `191`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `11`
- research_watch: `152`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18507`
- MARKET_INELIGIBLE_SINGLETON: `5997`
- UNSAFE_OR_UNVERIFIED_LOCATION: `353`
- HIGHSEC_RESTRICTED_CAPITAL: `58`
- FATAL_OR_ACCESS_UNVERIFIED: `18`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
- NO_EXECUTABLE_ITEMS: `2`
- LIST_DATA_INCOMPLETE: `2`
- SKIN_DOMINANT: `1`
