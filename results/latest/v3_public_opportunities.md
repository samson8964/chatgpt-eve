# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T13:31:39.994Z
- Market snapshot: 2026-10-09T13:18:36.041Z
- Candidate universe: 24395; deep validation pool: 241; feasible: 222
- FULL_CASH: 6
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 156
- FORMAL MAIL: 6

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50277`
- eligible_contracts: `43597`
- market_executable_contracts: `24395`
- snapshot_candidates: `24395`
- candidate_pool: `610`
- location_executable: `241`
- feasible: `222`
- full_cash: `6`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `11`
- research_watch: `156`
- mail_eligible: `6`

## Rejection reasons

- BPC_ROUTED: `18983`
- MARKET_INELIGIBLE_SINGLETON: `6221`
- UNSAFE_OR_UNVERIFIED_LOCATION: `369`
- HIGHSEC_RESTRICTED_CAPITAL: `16`
- FATAL_OR_ACCESS_UNVERIFIED: `11`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_TOO_SLOW: `5`
- SKIN_DOMINANT: `3`
- LIST_DATA_INCOMPLETE: `3`
