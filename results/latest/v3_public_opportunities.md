# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T13:31:39.994Z
- Market snapshot: 2026-10-09T13:48:39.461Z
- Candidate universe: 24392; deep validation pool: 249; feasible: 229
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 158
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

- raw_contracts: `50277`
- eligible_contracts: `43594`
- market_executable_contracts: `24392`
- snapshot_candidates: `24392`
- candidate_pool: `610`
- location_executable: `249`
- feasible: `229`
- full_cash: `5`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `158`
- mail_eligible: `4`

## Rejection reasons

- BPC_ROUTED: `18981`
- MARKET_INELIGIBLE_SINGLETON: `6223`
- UNSAFE_OR_UNVERIFIED_LOCATION: `361`
- HIGHSEC_RESTRICTED_CAPITAL: `16`
- FATAL_OR_ACCESS_UNVERIFIED: `11`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_TOO_SLOW: `5`
- SKIN_DOMINANT: `4`
- LIST_DATA_INCOMPLETE: `3`
