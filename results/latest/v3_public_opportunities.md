# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T17:31:24.735Z
- Market snapshot: 2026-10-10T17:48:39.362Z
- Candidate universe: 24776; deep validation pool: 268; feasible: 198
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
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

- raw_contracts: `50491`
- eligible_contracts: `43794`
- market_executable_contracts: `24776`
- snapshot_candidates: `24776`
- candidate_pool: `610`
- location_executable: `268`
- feasible: `198`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `160`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18792`
- MARKET_INELIGIBLE_SINGLETON: `6345`
- UNSAFE_OR_UNVERIFIED_LOCATION: `342`
- HIGHSEC_RESTRICTED_CAPITAL: `67`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- LIST_TOO_SLOW: `5`
- SKIN_DOMINANT: `2`
- NO_EXECUTABLE_ITEMS: `1`
