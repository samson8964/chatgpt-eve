# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T22:01:38.054Z
- Market snapshot: 2026-10-09T21:48:24.942Z
- Candidate universe: 24608; deep validation pool: 262; feasible: 197
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 159
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

- raw_contracts: `50323`
- eligible_contracts: `43668`
- market_executable_contracts: `24608`
- snapshot_candidates: `24608`
- candidate_pool: `610`
- location_executable: `262`
- feasible: `197`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `10`
- research_watch: `159`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18847`
- MARKET_INELIGIBLE_SINGLETON: `6210`
- UNSAFE_OR_UNVERIFIED_LOCATION: `348`
- HIGHSEC_RESTRICTED_CAPITAL: `64`
- BARTER_PROCUREMENT_INCOMPLETE: `9`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `3`
- SKIN_DOMINANT: `1`
