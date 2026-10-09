# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T19:01:49.860Z
- Market snapshot: 2026-10-09T19:18:31.907Z
- Candidate universe: 24482; deep validation pool: 251; feasible: 179
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 162
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

- raw_contracts: `50218`
- eligible_contracts: `43566`
- market_executable_contracts: `24482`
- snapshot_candidates: `24482`
- candidate_pool: `610`
- location_executable: `251`
- feasible: `179`
- full_cash: `1`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `4`
- research_watch: `162`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18875`
- MARKET_INELIGIBLE_SINGLETON: `6189`
- UNSAFE_OR_UNVERIFIED_LOCATION: `359`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
- SKIN_DOMINANT: `4`
- LIST_DATA_INCOMPLETE: `4`
