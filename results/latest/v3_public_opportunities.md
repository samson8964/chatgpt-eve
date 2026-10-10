# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T05:31:42.010Z
- Market snapshot: 2026-10-10T05:18:23.332Z
- Candidate universe: 24758; deep validation pool: 254; feasible: 193
- FULL_CASH: 6
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 161
- FORMAL MAIL: 7

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50436`
- eligible_contracts: `43854`
- market_executable_contracts: `24758`
- snapshot_candidates: `24758`
- candidate_pool: `610`
- location_executable: `254`
- feasible: `193`
- full_cash: `6`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `9`
- research_watch: `161`
- mail_eligible: `7`

## Rejection reasons

- BPC_ROUTED: `18877`
- MARKET_INELIGIBLE_SINGLETON: `6297`
- UNSAFE_OR_UNVERIFIED_LOCATION: `356`
- HIGHSEC_RESTRICTED_CAPITAL: `57`
- FATAL_OR_ACCESS_UNVERIFIED: `11`
- BARTER_PROCUREMENT_INCOMPLETE: `10`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
