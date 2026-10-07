# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T14:31:23.191Z
- Market snapshot: 2026-10-07T14:18:28.079Z
- Candidate universe: 24530; deep validation pool: 239; feasible: 175
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 155
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

- raw_contracts: `49821`
- eligible_contracts: `43237`
- market_executable_contracts: `24530`
- snapshot_candidates: `24530`
- candidate_pool: `605`
- location_executable: `239`
- feasible: `175`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `155`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18485`
- MARKET_INELIGIBLE_SINGLETON: `6004`
- UNSAFE_OR_UNVERIFIED_LOCATION: `366`
- HIGHSEC_RESTRICTED_CAPITAL: `60`
- FATAL_OR_ACCESS_UNVERIFIED: `16`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
- LIST_DATA_INCOMPLETE: `2`
