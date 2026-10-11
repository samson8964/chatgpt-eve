# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T15:01:51.532Z
- Market snapshot: 2026-10-11T15:18:48.413Z
- Candidate universe: 24501; deep validation pool: 271; feasible: 201
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
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

- raw_contracts: `50334`
- eligible_contracts: `43760`
- market_executable_contracts: `24501`
- snapshot_candidates: `24501`
- candidate_pool: `610`
- location_executable: `271`
- feasible: `201`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `161`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `19039`
- MARKET_INELIGIBLE_SINGLETON: `6210`
- UNSAFE_OR_UNVERIFIED_LOCATION: `339`
- HIGHSEC_RESTRICTED_CAPITAL: `65`
- BARTER_PROCUREMENT_INCOMPLETE: `9`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `4`
