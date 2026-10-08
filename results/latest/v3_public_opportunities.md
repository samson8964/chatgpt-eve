# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T07:02:43.972Z
- Market snapshot: 2026-10-08T07:18:29.843Z
- Candidate universe: 24557; deep validation pool: 227; feasible: 214
- FULL_CASH: 6
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 12
- RESEARCH: 151
- FORMAL MAIL: 6

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `49889`
- eligible_contracts: `43337`
- market_executable_contracts: `24557`
- snapshot_candidates: `24557`
- candidate_pool: `605`
- location_executable: `227`
- feasible: `214`
- full_cash: `6`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `12`
- research_watch: `151`
- mail_eligible: `6`

## Rejection reasons

- BPC_ROUTED: `18554`
- MARKET_INELIGIBLE_SINGLETON: `5991`
- UNSAFE_OR_UNVERIFIED_LOCATION: `378`
- HIGHSEC_RESTRICTED_CAPITAL: `11`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
- LIST_DATA_INCOMPLETE: `3`
- SKIN_DOMINANT: `2`
