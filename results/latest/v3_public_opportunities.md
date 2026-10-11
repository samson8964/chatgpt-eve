# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T00:31:37.420Z
- Market snapshot: 2026-10-11T00:48:46.097Z
- Candidate universe: 24605; deep validation pool: 281; feasible: 206
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 156
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

- raw_contracts: `50267`
- eligible_contracts: `43731`
- market_executable_contracts: `24605`
- snapshot_candidates: `24605`
- candidate_pool: `610`
- location_executable: `281`
- feasible: `206`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `11`
- research_watch: `156`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18903`
- MARKET_INELIGIBLE_SINGLETON: `6232`
- UNSAFE_OR_UNVERIFIED_LOCATION: `329`
- HIGHSEC_RESTRICTED_CAPITAL: `70`
- FATAL_OR_ACCESS_UNVERIFIED: `13`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `3`
