# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T04:32:00.983Z
- Market snapshot: 2026-10-10T04:18:22.750Z
- Candidate universe: 24679; deep validation pool: 258; feasible: 183
- FULL_CASH: 7
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 158
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

- raw_contracts: `50406`
- eligible_contracts: `43735`
- market_executable_contracts: `24679`
- snapshot_candidates: `24679`
- candidate_pool: `610`
- location_executable: `258`
- feasible: `183`
- full_cash: `7`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `8`
- research_watch: `158`
- mail_eligible: `7`

## Rejection reasons

- BPC_ROUTED: `18844`
- MARKET_INELIGIBLE_SINGLETON: `6274`
- UNSAFE_OR_UNVERIFIED_LOCATION: `352`
- HIGHSEC_RESTRICTED_CAPITAL: `70`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- SKIN_DOMINANT: `3`
- NO_EXECUTABLE_ITEMS: `2`
