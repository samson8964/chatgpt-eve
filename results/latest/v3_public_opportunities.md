# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T22:31:50.701Z
- Market snapshot: 2026-10-07T22:48:26.492Z
- Candidate universe: 24519; deep validation pool: 224; feasible: 211
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 155
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

- raw_contracts: `49946`
- eligible_contracts: `43379`
- market_executable_contracts: `24519`
- snapshot_candidates: `24519`
- candidate_pool: `605`
- location_executable: `224`
- feasible: `211`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `155`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18633`
- MARKET_INELIGIBLE_SINGLETON: `5996`
- UNSAFE_OR_UNVERIFIED_LOCATION: `381`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- HIGHSEC_RESTRICTED_CAPITAL: `9`
- SKIN_DOMINANT: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
- LIST_DATA_INCOMPLETE: `3`
