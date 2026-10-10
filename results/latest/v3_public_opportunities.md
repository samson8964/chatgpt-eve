# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T01:31:38.550Z
- Market snapshot: 2026-10-10T01:18:24.155Z
- Candidate universe: 24704; deep validation pool: 292; feasible: 218
- FULL_CASH: 6
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 156
- FORMAL MAIL: 7

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50445`
- eligible_contracts: `43804`
- market_executable_contracts: `24704`
- snapshot_candidates: `24704`
- candidate_pool: `610`
- location_executable: `292`
- feasible: `218`
- full_cash: `6`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `10`
- research_watch: `156`
- mail_eligible: `7`

## Rejection reasons

- BPC_ROUTED: `18891`
- MARKET_INELIGIBLE_SINGLETON: `6280`
- UNSAFE_OR_UNVERIFIED_LOCATION: `318`
- HIGHSEC_RESTRICTED_CAPITAL: `71`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
