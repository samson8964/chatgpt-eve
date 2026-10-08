# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T09:31:23.353Z
- Market snapshot: 2026-10-08T09:18:30.384Z
- Candidate universe: 24576; deep validation pool: 226; feasible: 160
- FULL_CASH: 8
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 17
- RESEARCH: 130
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

- raw_contracts: `49887`
- eligible_contracts: `43335`
- market_executable_contracts: `24576`
- snapshot_candidates: `24576`
- candidate_pool: `605`
- location_executable: `226`
- feasible: `160`
- full_cash: `8`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `17`
- research_watch: `130`
- mail_eligible: `7`

## Rejection reasons

- BPC_ROUTED: `18530`
- MARKET_INELIGIBLE_SINGLETON: `5998`
- UNSAFE_OR_UNVERIFIED_LOCATION: `379`
- HIGHSEC_RESTRICTED_CAPITAL: `65`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- SKIN_DOMINANT: `1`
