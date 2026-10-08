# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T02:31:37.636Z
- Market snapshot: 2026-10-08T02:18:19.290Z
- Candidate universe: 24553; deep validation pool: 237; feasible: 187
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 155
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

- raw_contracts: `49932`
- eligible_contracts: `43410`
- market_executable_contracts: `24553`
- snapshot_candidates: `24553`
- candidate_pool: `605`
- location_executable: `237`
- feasible: `187`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `155`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18636`
- MARKET_INELIGIBLE_SINGLETON: `5993`
- UNSAFE_OR_UNVERIFIED_LOCATION: `368`
- HIGHSEC_RESTRICTED_CAPITAL: `49`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `2`
- SKIN_DOMINANT: `1`
