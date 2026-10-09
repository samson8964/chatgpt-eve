# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T09:02:04.951Z
- Market snapshot: 2026-10-09T09:18:33.664Z
- Candidate universe: 24204; deep validation pool: 266; feasible: 203
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 162
- FORMAL MAIL: 3

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50076`
- eligible_contracts: `43322`
- market_executable_contracts: `24204`
- snapshot_candidates: `24204`
- candidate_pool: `610`
- location_executable: `266`
- feasible: `203`
- full_cash: `3`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `5`
- research_watch: `162`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18893`
- MARKET_INELIGIBLE_SINGLETON: `6048`
- UNSAFE_OR_UNVERIFIED_LOCATION: `344`
- HIGHSEC_RESTRICTED_CAPITAL: `59`
- FATAL_OR_ACCESS_UNVERIFIED: `19`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `3`
