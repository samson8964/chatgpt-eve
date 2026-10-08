# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T15:31:31.339Z
- Market snapshot: 2026-10-08T15:48:51.102Z
- Candidate universe: 24584; deep validation pool: 238; feasible: 169
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 3
- RESEARCH: 159
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

- raw_contracts: `50088`
- eligible_contracts: `43553`
- market_executable_contracts: `24584`
- snapshot_candidates: `24584`
- candidate_pool: `606`
- location_executable: `238`
- feasible: `169`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `3`
- research_watch: `159`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18743`
- MARKET_INELIGIBLE_SINGLETON: `6101`
- UNSAFE_OR_UNVERIFIED_LOCATION: `368`
- HIGHSEC_RESTRICTED_CAPITAL: `65`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- LIST_DATA_INCOMPLETE: `5`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
