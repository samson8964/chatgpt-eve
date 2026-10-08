# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T14:31:39.568Z
- Market snapshot: 2026-10-08T14:18:35.224Z
- Candidate universe: 24593; deep validation pool: 266; feasible: 196
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 2
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 156
- FORMAL MAIL: 5

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50000`
- eligible_contracts: `43521`
- market_executable_contracts: `24593`
- snapshot_candidates: `24593`
- candidate_pool: `606`
- location_executable: `266`
- feasible: `196`
- full_cash: `5`
- partial_cash_floor: `2`
- barter: `0`
- list_supported: `6`
- research_watch: `156`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18699`
- MARKET_INELIGIBLE_SINGLETON: `6099`
- UNSAFE_OR_UNVERIFIED_LOCATION: `340`
- HIGHSEC_RESTRICTED_CAPITAL: `66`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
