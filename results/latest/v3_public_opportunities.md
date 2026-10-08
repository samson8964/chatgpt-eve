# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T04:31:56.307Z
- Market snapshot: 2026-10-08T04:48:24.084Z
- Candidate universe: 24530; deep validation pool: 255; feasible: 237
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 155
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

- raw_contracts: `49858`
- eligible_contracts: `43324`
- market_executable_contracts: `24530`
- snapshot_candidates: `24530`
- candidate_pool: `605`
- location_executable: `255`
- feasible: `237`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `155`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18567`
- MARKET_INELIGIBLE_SINGLETON: `5988`
- UNSAFE_OR_UNVERIFIED_LOCATION: `350`
- HIGHSEC_RESTRICTED_CAPITAL: `16`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- LIST_TOO_SLOW: `3`
- SKIN_DOMINANT: `2`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
