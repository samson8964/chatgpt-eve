# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T18:31:23.350Z
- Market snapshot: 2026-10-07T18:18:28.141Z
- Candidate universe: 24537; deep validation pool: 212; feasible: 148
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 133
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

- raw_contracts: `49687`
- eligible_contracts: `43211`
- market_executable_contracts: `24537`
- snapshot_candidates: `24537`
- candidate_pool: `605`
- location_executable: `212`
- feasible: `148`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `133`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18454`
- MARKET_INELIGIBLE_SINGLETON: `5994`
- UNSAFE_OR_UNVERIFIED_LOCATION: `393`
- HIGHSEC_RESTRICTED_CAPITAL: `60`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
