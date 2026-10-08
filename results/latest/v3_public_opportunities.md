# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T08:31:42.385Z
- Market snapshot: 2026-10-08T08:48:29.430Z
- Candidate universe: 24556; deep validation pool: 233; feasible: 223
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 157
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

- raw_contracts: `49897`
- eligible_contracts: `43340`
- market_executable_contracts: `24556`
- snapshot_candidates: `24556`
- candidate_pool: `605`
- location_executable: `233`
- feasible: `223`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `157`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18554`
- MARKET_INELIGIBLE_SINGLETON: `5989`
- UNSAFE_OR_UNVERIFIED_LOCATION: `372`
- HIGHSEC_RESTRICTED_CAPITAL: `7`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `2`
- LIST_DATA_INCOMPLETE: `2`
