# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T22:31:36.279Z
- Market snapshot: 2026-10-09T22:48:31.641Z
- Candidate universe: 24590; deep validation pool: 262; feasible: 191
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 160
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

- raw_contracts: `50318`
- eligible_contracts: `43649`
- market_executable_contracts: `24590`
- snapshot_candidates: `24590`
- candidate_pool: `610`
- location_executable: `262`
- feasible: `191`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `160`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18845`
- MARKET_INELIGIBLE_SINGLETON: `6201`
- UNSAFE_OR_UNVERIFIED_LOCATION: `348`
- HIGHSEC_RESTRICTED_CAPITAL: `66`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- SKIN_DOMINANT: `5`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `3`
- LIST_DATA_INCOMPLETE: `1`
