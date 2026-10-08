# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T13:01:55.055Z
- Market snapshot: 2026-10-08T12:49:02.748Z
- Candidate universe: 24562; deep validation pool: 266; feasible: 199
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 153
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

- raw_contracts: `49971`
- eligible_contracts: `43376`
- market_executable_contracts: `24562`
- snapshot_candidates: `24562`
- candidate_pool: `606`
- location_executable: `266`
- feasible: `199`
- full_cash: `3`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `9`
- research_watch: `153`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18583`
- MARKET_INELIGIBLE_SINGLETON: `6054`
- UNSAFE_OR_UNVERIFIED_LOCATION: `340`
- HIGHSEC_RESTRICTED_CAPITAL: `65`
- FATAL_OR_ACCESS_UNVERIFIED: `3`
- SKIN_DOMINANT: `2`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
- LIST_TOO_SLOW: `2`
