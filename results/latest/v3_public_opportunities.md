# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T15:31:26.824Z
- Market snapshot: 2026-10-09T15:48:36.299Z
- Candidate universe: 24393; deep validation pool: 272; feasible: 198
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 3
- RESEARCH: 163
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

- raw_contracts: `50211`
- eligible_contracts: `43518`
- market_executable_contracts: `24393`
- snapshot_candidates: `24393`
- candidate_pool: `610`
- location_executable: `272`
- feasible: `198`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `3`
- research_watch: `163`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18917`
- MARKET_INELIGIBLE_SINGLETON: `6187`
- UNSAFE_OR_UNVERIFIED_LOCATION: `338`
- HIGHSEC_RESTRICTED_CAPITAL: `70`
- FATAL_OR_ACCESS_UNVERIFIED: `15`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
