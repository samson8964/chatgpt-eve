# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T16:31:44.833Z
- Market snapshot: 2026-10-10T16:48:43.278Z
- Candidate universe: 24595; deep validation pool: 265; feasible: 189
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 161
- FORMAL MAIL: 0

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50401`
- eligible_contracts: `43631`
- market_executable_contracts: `24595`
- snapshot_candidates: `24595`
- candidate_pool: `610`
- location_executable: `265`
- feasible: `189`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `161`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18817`
- MARKET_INELIGIBLE_SINGLETON: `6284`
- UNSAFE_OR_UNVERIFIED_LOCATION: `345`
- HIGHSEC_RESTRICTED_CAPITAL: `70`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `4`
- NO_EXECUTABLE_ITEMS: `1`
- LIST_DATA_INCOMPLETE: `1`
