# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T04:01:38.138Z
- Market snapshot: 2026-10-11T04:18:33.316Z
- Candidate universe: 24625; deep validation pool: 281; feasible: 205
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 11
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

- raw_contracts: `50205`
- eligible_contracts: `43705`
- market_executable_contracts: `24625`
- snapshot_candidates: `24625`
- candidate_pool: `610`
- location_executable: `281`
- feasible: `205`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `11`
- research_watch: `155`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18855`
- MARKET_INELIGIBLE_SINGLETON: `6223`
- UNSAFE_OR_UNVERIFIED_LOCATION: `329`
- HIGHSEC_RESTRICTED_CAPITAL: `71`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `3`
