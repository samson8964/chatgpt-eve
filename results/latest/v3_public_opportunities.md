# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T02:01:27.910Z
- Market snapshot: 2026-10-10T02:18:24.185Z
- Candidate universe: 24698; deep validation pool: 292; feasible: 230
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 160
- FORMAL MAIL: 3

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50447`
- eligible_contracts: `43771`
- market_executable_contracts: `24698`
- snapshot_candidates: `24698`
- candidate_pool: `610`
- location_executable: `292`
- feasible: `230`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `160`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18860`
- MARKET_INELIGIBLE_SINGLETON: `6282`
- UNSAFE_OR_UNVERIFIED_LOCATION: `318`
- HIGHSEC_RESTRICTED_CAPITAL: `58`
- BARTER_PROCUREMENT_INCOMPLETE: `9`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `3`
