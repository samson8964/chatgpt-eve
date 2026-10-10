# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T13:31:43.088Z
- Market snapshot: 2026-10-10T13:48:42.641Z
- Candidate universe: 24614; deep validation pool: 258; feasible: 184
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 161
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

- raw_contracts: `50290`
- eligible_contracts: `43718`
- market_executable_contracts: `24614`
- snapshot_candidates: `24614`
- candidate_pool: `610`
- location_executable: `258`
- feasible: `184`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `161`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18879`
- MARKET_INELIGIBLE_SINGLETON: `6260`
- UNSAFE_OR_UNVERIFIED_LOCATION: `352`
- HIGHSEC_RESTRICTED_CAPITAL: `71`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- LIST_TOO_SLOW: `5`
- SKIN_DOMINANT: `3`
