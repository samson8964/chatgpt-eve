# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T00:01:41.842Z
- Market snapshot: 2026-10-09T23:48:28.592Z
- Candidate universe: 24646; deep validation pool: 288; feasible: 223
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 156
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

- raw_contracts: `50344`
- eligible_contracts: `43703`
- market_executable_contracts: `24646`
- snapshot_candidates: `24646`
- candidate_pool: `610`
- location_executable: `288`
- feasible: `223`
- full_cash: `4`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `11`
- research_watch: `156`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18845`
- MARKET_INELIGIBLE_SINGLETON: `6228`
- UNSAFE_OR_UNVERIFIED_LOCATION: `322`
- HIGHSEC_RESTRICTED_CAPITAL: `62`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
