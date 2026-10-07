# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T21:31:40.502Z
- Market snapshot: 2026-10-07T22:18:27.127Z
- Candidate universe: 24522; deep validation pool: 223; feasible: 159
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 142
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

- raw_contracts: `49925`
- eligible_contracts: `43363`
- market_executable_contracts: `24522`
- snapshot_candidates: `24522`
- candidate_pool: `605`
- location_executable: `223`
- feasible: `159`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `142`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18619`
- MARKET_INELIGIBLE_SINGLETON: `6002`
- UNSAFE_OR_UNVERIFIED_LOCATION: `382`
- HIGHSEC_RESTRICTED_CAPITAL: `60`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
