# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T17:01:46.272Z
- Market snapshot: 2026-10-11T17:18:40.055Z
- Candidate universe: 24690; deep validation pool: 258; feasible: 186
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 160
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

- raw_contracts: `50529`
- eligible_contracts: `43889`
- market_executable_contracts: `24690`
- snapshot_candidates: `24690`
- candidate_pool: `611`
- location_executable: `258`
- feasible: `186`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `160`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18970`
- MARKET_INELIGIBLE_SINGLETON: `6378`
- UNSAFE_OR_UNVERIFIED_LOCATION: `353`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- FATAL_OR_ACCESS_UNVERIFIED: `3`
