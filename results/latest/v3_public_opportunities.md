# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T15:31:45.114Z
- Market snapshot: 2026-10-10T15:48:45.021Z
- Candidate universe: 24580; deep validation pool: 258; feasible: 181
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 157
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

- raw_contracts: `50410`
- eligible_contracts: `43698`
- market_executable_contracts: `24580`
- snapshot_candidates: `24580`
- candidate_pool: `610`
- location_executable: `258`
- feasible: `181`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `10`
- research_watch: `157`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18895`
- MARKET_INELIGIBLE_SINGLETON: `6282`
- UNSAFE_OR_UNVERIFIED_LOCATION: `352`
- HIGHSEC_RESTRICTED_CAPITAL: `72`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_TOO_SLOW: `5`
- LIST_DATA_INCOMPLETE: `5`
- SKIN_DOMINANT: `3`
- NO_EXECUTABLE_ITEMS: `2`
