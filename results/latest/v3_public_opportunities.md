# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T07:02:43.972Z
- Market snapshot: 2026-10-08T06:49:02.275Z
- Candidate universe: 24558; deep validation pool: 222; feasible: 154
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 136
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

- raw_contracts: `49889`
- eligible_contracts: `43338`
- market_executable_contracts: `24558`
- snapshot_candidates: `24558`
- candidate_pool: `605`
- location_executable: `222`
- feasible: `154`
- full_cash: `5`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `7`
- research_watch: `136`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18554`
- MARKET_INELIGIBLE_SINGLETON: `5994`
- UNSAFE_OR_UNVERIFIED_LOCATION: `383`
- HIGHSEC_RESTRICTED_CAPITAL: `65`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- SKIN_DOMINANT: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
