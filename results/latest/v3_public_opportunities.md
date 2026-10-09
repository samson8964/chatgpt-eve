# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T06:02:18.204Z
- Market snapshot: 2026-10-09T05:48:24.320Z
- Candidate universe: 24268; deep validation pool: 241; feasible: 171
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 145
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

- raw_contracts: `50092`
- eligible_contracts: `43301`
- market_executable_contracts: `24268`
- snapshot_candidates: `24268`
- candidate_pool: `607`
- location_executable: `241`
- feasible: `171`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `10`
- research_watch: `145`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18812`
- MARKET_INELIGIBLE_SINGLETON: `6050`
- UNSAFE_OR_UNVERIFIED_LOCATION: `366`
- HIGHSEC_RESTRICTED_CAPITAL: `65`
- FATAL_OR_ACCESS_UNVERIFIED: `14`
- LIST_DATA_INCOMPLETE: `5`
- SKIN_DOMINANT: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
- NO_EXECUTABLE_ITEMS: `2`
