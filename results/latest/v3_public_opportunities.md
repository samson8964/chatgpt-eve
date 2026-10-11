# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T22:31:42.578Z
- Market snapshot: 2026-10-11T22:48:44.317Z
- Candidate universe: 24904; deep validation pool: 262; feasible: 178
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 3
- RESEARCH: 163
- FORMAL MAIL: 1

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50890`
- eligible_contracts: `44203`
- market_executable_contracts: `24904`
- snapshot_candidates: `24904`
- candidate_pool: `612`
- location_executable: `262`
- feasible: `178`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `3`
- research_watch: `163`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19063`
- MARKET_INELIGIBLE_SINGLETON: `6462`
- UNSAFE_OR_UNVERIFIED_LOCATION: `350`
- HIGHSEC_RESTRICTED_CAPITAL: `79`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `3`
- FATAL_OR_ACCESS_UNVERIFIED: `1`
