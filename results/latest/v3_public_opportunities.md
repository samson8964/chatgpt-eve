# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T17:31:27.216Z
- Market snapshot: 2026-10-08T17:48:45.502Z
- Candidate universe: 24474; deep validation pool: 278; feasible: 204
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 3
- RESEARCH: 159
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

- raw_contracts: `50088`
- eligible_contracts: `43471`
- market_executable_contracts: `24474`
- snapshot_candidates: `24474`
- candidate_pool: `607`
- location_executable: `278`
- feasible: `204`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `3`
- research_watch: `159`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18771`
- MARKET_INELIGIBLE_SINGLETON: `6107`
- UNSAFE_OR_UNVERIFIED_LOCATION: `329`
- HIGHSEC_RESTRICTED_CAPITAL: `70`
- FATAL_OR_ACCESS_UNVERIFIED: `20`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
