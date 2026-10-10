# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T00:31:41.588Z
- Market snapshot: 2026-10-10T00:18:25.621Z
- Candidate universe: 24629; deep validation pool: 307; feasible: 293
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 161
- FORMAL MAIL: 2

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50375`
- eligible_contracts: `43726`
- market_executable_contracts: `24629`
- snapshot_candidates: `24629`
- candidate_pool: `610`
- location_executable: `307`
- feasible: `293`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `161`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18885`
- MARKET_INELIGIBLE_SINGLETON: `6240`
- UNSAFE_OR_UNVERIFIED_LOCATION: `303`
- BARTER_PROCUREMENT_INCOMPLETE: `9`
- HIGHSEC_RESTRICTED_CAPITAL: `8`
- SKIN_DOMINANT: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `3`
