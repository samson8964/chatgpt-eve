# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T13:01:55.055Z
- Market snapshot: 2026-10-08T13:18:34.851Z
- Candidate universe: 24557; deep validation pool: 265; feasible: 198
- FULL_CASH: 8
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 152
- FORMAL MAIL: 8

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `49976`
- eligible_contracts: `43355`
- market_executable_contracts: `24557`
- snapshot_candidates: `24557`
- candidate_pool: `606`
- location_executable: `265`
- feasible: `198`
- full_cash: `8`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `11`
- research_watch: `152`
- mail_eligible: `8`

## Rejection reasons

- BPC_ROUTED: `18570`
- MARKET_INELIGIBLE_SINGLETON: `6065`
- UNSAFE_OR_UNVERIFIED_LOCATION: `341`
- HIGHSEC_RESTRICTED_CAPITAL: `64`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- SKIN_DOMINANT: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
