# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T21:01:37.962Z
- Market snapshot: 2026-10-09T21:18:30.842Z
- Candidate universe: 24590; deep validation pool: 317; feasible: 245
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 3
- RESEARCH: 163
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

- raw_contracts: `50326`
- eligible_contracts: `43692`
- market_executable_contracts: `24590`
- snapshot_candidates: `24590`
- candidate_pool: `610`
- location_executable: `317`
- feasible: `245`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `3`
- research_watch: `163`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18888`
- MARKET_INELIGIBLE_SINGLETON: `6225`
- UNSAFE_OR_UNVERIFIED_LOCATION: `293`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `3`
