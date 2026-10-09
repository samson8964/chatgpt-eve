# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T17:31:50.961Z
- Market snapshot: 2026-10-09T17:48:41.407Z
- Candidate universe: 24387; deep validation pool: 254; feasible: 186
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 159
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

- raw_contracts: `50238`
- eligible_contracts: `43463`
- market_executable_contracts: `24387`
- snapshot_candidates: `24387`
- candidate_pool: `610`
- location_executable: `254`
- feasible: `186`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `159`
- mail_eligible: `4`

## Rejection reasons

- BPC_ROUTED: `18872`
- MARKET_INELIGIBLE_SINGLETON: `6190`
- UNSAFE_OR_UNVERIFIED_LOCATION: `356`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- FATAL_OR_ACCESS_UNVERIFIED: `12`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_TOO_SLOW: `6`
- LIST_DATA_INCOMPLETE: `3`
