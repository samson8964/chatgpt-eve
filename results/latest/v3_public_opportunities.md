# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T08:01:41.046Z
- Market snapshot: 2026-10-08T07:48:33.970Z
- Candidate universe: 24553; deep validation pool: 223; feasible: 156
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 138
- FORMAL MAIL: 3

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `49929`
- eligible_contracts: `43365`
- market_executable_contracts: `24553`
- snapshot_candidates: `24553`
- candidate_pool: `605`
- location_executable: `223`
- feasible: `156`
- full_cash: `3`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `8`
- research_watch: `138`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18586`
- MARKET_INELIGIBLE_SINGLETON: `5986`
- UNSAFE_OR_UNVERIFIED_LOCATION: `382`
- HIGHSEC_RESTRICTED_CAPITAL: `63`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
