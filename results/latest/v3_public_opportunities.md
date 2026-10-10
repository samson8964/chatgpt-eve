# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T07:31:41.150Z
- Market snapshot: 2026-10-10T07:48:27.063Z
- Candidate universe: 24749; deep validation pool: 247; feasible: 176
- FULL_CASH: 7
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 152
- FORMAL MAIL: 8

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50414`
- eligible_contracts: `43795`
- market_executable_contracts: `24749`
- snapshot_candidates: `24749`
- candidate_pool: `610`
- location_executable: `247`
- feasible: `176`
- full_cash: `7`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `11`
- research_watch: `152`
- mail_eligible: `8`

## Rejection reasons

- BPC_ROUTED: `18831`
- MARKET_INELIGIBLE_SINGLETON: `6278`
- UNSAFE_OR_UNVERIFIED_LOCATION: `363`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_DATA_INCOMPLETE: `5`
- LIST_TOO_SLOW: `4`
- NO_EXECUTABLE_ITEMS: `2`
- SKIN_DOMINANT: `1`
