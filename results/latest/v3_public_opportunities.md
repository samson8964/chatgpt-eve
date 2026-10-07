# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T21:01:38.461Z
- Market snapshot: 2026-10-07T20:48:25.478Z
- Candidate universe: 24539; deep validation pool: 224; feasible: 162
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 147
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

- raw_contracts: `49950`
- eligible_contracts: `43382`
- market_executable_contracts: `24539`
- snapshot_candidates: `24539`
- candidate_pool: `605`
- location_executable: `224`
- feasible: `162`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `147`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18624`
- MARKET_INELIGIBLE_SINGLETON: `6002`
- UNSAFE_OR_UNVERIFIED_LOCATION: `381`
- HIGHSEC_RESTRICTED_CAPITAL: `59`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `5`
- LIST_DATA_INCOMPLETE: `4`
- NO_EXECUTABLE_ITEMS: `2`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
- SKIN_DOMINANT: `1`
