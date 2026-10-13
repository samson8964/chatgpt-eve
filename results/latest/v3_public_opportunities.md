# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-13T02:31:38.994Z
- Market snapshot: 2026-10-13T02:18:27.073Z
- Candidate universe: 25041; deep validation pool: 264; feasible: 178
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 156
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

- raw_contracts: `50688`
- eligible_contracts: `44468`
- market_executable_contracts: `25041`
- snapshot_candidates: `25041`
- candidate_pool: `612`
- location_executable: `264`
- feasible: `178`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `156`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19204`
- MARKET_INELIGIBLE_SINGLETON: `6436`
- UNSAFE_OR_UNVERIFIED_LOCATION: `348`
- HIGHSEC_RESTRICTED_CAPITAL: `78`
- FATAL_OR_ACCESS_UNVERIFIED: `16`
- SKIN_DOMINANT: `8`
- LIST_DATA_INCOMPLETE: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
