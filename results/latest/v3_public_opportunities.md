# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T00:31:38.423Z
- Market snapshot: 2026-10-08T00:18:20.760Z
- Candidate universe: 24547; deep validation pool: 230; feasible: 209
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 3
- RESEARCH: 159
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

- raw_contracts: `49961`
- eligible_contracts: `43403`
- market_executable_contracts: `24547`
- snapshot_candidates: `24547`
- candidate_pool: `605`
- location_executable: `230`
- feasible: `209`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `3`
- research_watch: `159`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18633`
- MARKET_INELIGIBLE_SINGLETON: `5998`
- UNSAFE_OR_UNVERIFIED_LOCATION: `375`
- HIGHSEC_RESTRICTED_CAPITAL: `17`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
