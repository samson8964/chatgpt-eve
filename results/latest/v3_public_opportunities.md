# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T13:31:41.111Z
- Market snapshot: 2026-10-11T13:48:35.824Z
- Candidate universe: 24529; deep validation pool: 266; feasible: 190
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 161
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

- raw_contracts: `50325`
- eligible_contracts: `43745`
- market_executable_contracts: `24529`
- snapshot_candidates: `24529`
- candidate_pool: `610`
- location_executable: `266`
- feasible: `190`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `5`
- research_watch: `161`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18992`
- MARKET_INELIGIBLE_SINGLETON: `6205`
- UNSAFE_OR_UNVERIFIED_LOCATION: `344`
- HIGHSEC_RESTRICTED_CAPITAL: `71`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `1`
