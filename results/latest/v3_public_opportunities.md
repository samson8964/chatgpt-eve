# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T03:31:36.736Z
- Market snapshot: 2026-10-10T03:18:21.907Z
- Candidate universe: 24682; deep validation pool: 263; feasible: 189
- FULL_CASH: 6
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 157
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

- raw_contracts: `50428`
- eligible_contracts: `43763`
- market_executable_contracts: `24682`
- snapshot_candidates: `24682`
- candidate_pool: `610`
- location_executable: `263`
- feasible: `189`
- full_cash: `6`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `10`
- research_watch: `157`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18869`
- MARKET_INELIGIBLE_SINGLETON: `6277`
- UNSAFE_OR_UNVERIFIED_LOCATION: `347`
- HIGHSEC_RESTRICTED_CAPITAL: `70`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `3`
- NO_EXECUTABLE_ITEMS: `2`
- SKIN_DOMINANT: `2`
- LIST_DATA_INCOMPLETE: `1`
