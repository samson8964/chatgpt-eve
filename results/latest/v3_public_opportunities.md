# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T14:31:41.694Z
- Market snapshot: 2026-10-09T14:48:40.663Z
- Candidate universe: 24420; deep validation pool: 249; feasible: 229
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 162
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

- raw_contracts: `50233`
- eligible_contracts: `43548`
- market_executable_contracts: `24420`
- snapshot_candidates: `24420`
- candidate_pool: `610`
- location_executable: `249`
- feasible: `229`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `5`
- research_watch: `162`
- mail_eligible: `4`

## Rejection reasons

- BPC_ROUTED: `18908`
- MARKET_INELIGIBLE_SINGLETON: `6205`
- UNSAFE_OR_UNVERIFIED_LOCATION: `361`
- HIGHSEC_RESTRICTED_CAPITAL: `18`
- FATAL_OR_ACCESS_UNVERIFIED: `14`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_TOO_SLOW: `6`
- LIST_DATA_INCOMPLETE: `3`
- SKIN_DOMINANT: `2`
