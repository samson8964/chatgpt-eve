# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T18:01:27.042Z
- Market snapshot: 2026-10-09T18:18:36.941Z
- Candidate universe: 24466; deep validation pool: 262; feasible: 186
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 161
- FORMAL MAIL: 2

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50273`
- eligible_contracts: `43539`
- market_executable_contracts: `24466`
- snapshot_candidates: `24466`
- candidate_pool: `610`
- location_executable: `262`
- feasible: `186`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `5`
- research_watch: `161`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18865`
- MARKET_INELIGIBLE_SINGLETON: `6202`
- UNSAFE_OR_UNVERIFIED_LOCATION: `348`
- HIGHSEC_RESTRICTED_CAPITAL: `71`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- FATAL_OR_ACCESS_UNVERIFIED: `3`
- NO_EXECUTABLE_ITEMS: `1`
