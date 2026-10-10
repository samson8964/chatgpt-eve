# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T04:32:00.983Z
- Market snapshot: 2026-10-10T04:48:27.087Z
- Candidate universe: 24676; deep validation pool: 257; feasible: 183
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 2
- BARTER: 0
- LIST-SUPPORTED: 12
- RESEARCH: 155
- FORMAL MAIL: 4

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
- eligible_contracts: `43722`
- market_executable_contracts: `24676`
- snapshot_candidates: `24676`
- candidate_pool: `610`
- location_executable: `257`
- feasible: `183`
- full_cash: `2`
- partial_cash_floor: `2`
- barter: `0`
- list_supported: `12`
- research_watch: `155`
- mail_eligible: `4`

## Rejection reasons

- BPC_ROUTED: `18833`
- MARKET_INELIGIBLE_SINGLETON: `6274`
- UNSAFE_OR_UNVERIFIED_LOCATION: `353`
- HIGHSEC_RESTRICTED_CAPITAL: `69`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `5`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
