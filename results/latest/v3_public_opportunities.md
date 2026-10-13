# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-13T01:31:41.291Z
- Market snapshot: 2026-10-13T01:48:42.885Z
- Candidate universe: 25082; deep validation pool: 239; feasible: 161
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 138
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

- raw_contracts: `50731`
- eligible_contracts: `44478`
- market_executable_contracts: `25082`
- snapshot_candidates: `25082`
- candidate_pool: `612`
- location_executable: `239`
- feasible: `161`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `5`
- research_watch: `138`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19173`
- MARKET_INELIGIBLE_SINGLETON: `6442`
- UNSAFE_OR_UNVERIFIED_LOCATION: `373`
- HIGHSEC_RESTRICTED_CAPITAL: `72`
- FATAL_OR_ACCESS_UNVERIFIED: `16`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `6`
- LIST_DATA_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
