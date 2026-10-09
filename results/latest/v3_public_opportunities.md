# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T18:31:24.785Z
- Market snapshot: 2026-10-09T18:18:36.941Z
- Candidate universe: 24474; deep validation pool: 239; feasible: 169
- FULL_CASH: 6
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 153
- FORMAL MAIL: 5

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50234`
- eligible_contracts: `43599`
- market_executable_contracts: `24474`
- snapshot_candidates: `24474`
- candidate_pool: `610`
- location_executable: `239`
- feasible: `169`
- full_cash: `6`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `6`
- research_watch: `153`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18916`
- MARKET_INELIGIBLE_SINGLETON: `6197`
- UNSAFE_OR_UNVERIFIED_LOCATION: `371`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_DATA_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
- FATAL_OR_ACCESS_UNVERIFIED: `3`
- SKIN_DOMINANT: `2`
