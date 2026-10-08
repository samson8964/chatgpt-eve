# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T08:31:42.385Z
- Market snapshot: 2026-10-08T08:18:28.500Z
- Candidate universe: 24561; deep validation pool: 232; feasible: 165
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 13
- RESEARCH: 142
- FORMAL MAIL: 0

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `49897`
- eligible_contracts: `43341`
- market_executable_contracts: `24561`
- snapshot_candidates: `24561`
- candidate_pool: `605`
- location_executable: `232`
- feasible: `165`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `13`
- research_watch: `142`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18554`
- MARKET_INELIGIBLE_SINGLETON: `5986`
- UNSAFE_OR_UNVERIFIED_LOCATION: `373`
- HIGHSEC_RESTRICTED_CAPITAL: `62`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- SKIN_DOMINANT: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- NO_EXECUTABLE_ITEMS: `2`
