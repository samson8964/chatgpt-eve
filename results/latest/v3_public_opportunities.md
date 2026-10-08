# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T10:01:35.827Z
- Market snapshot: 2026-10-08T10:18:34.833Z
- Candidate universe: 24596; deep validation pool: 235; feasible: 216
- FULL_CASH: 6
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 155
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

- raw_contracts: `49939`
- eligible_contracts: `43374`
- market_executable_contracts: `24596`
- snapshot_candidates: `24596`
- candidate_pool: `605`
- location_executable: `235`
- feasible: `216`
- full_cash: `6`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `8`
- research_watch: `155`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18548`
- MARKET_INELIGIBLE_SINGLETON: `6006`
- UNSAFE_OR_UNVERIFIED_LOCATION: `370`
- HIGHSEC_RESTRICTED_CAPITAL: `17`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
- SKIN_DOMINANT: `2`
- LIST_DATA_INCOMPLETE: `2`
