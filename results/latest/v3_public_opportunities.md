# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T21:31:43.427Z
- Market snapshot: 2026-10-09T21:48:24.942Z
- Candidate universe: 24597; deep validation pool: 294; feasible: 220
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 159
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

- raw_contracts: `50338`
- eligible_contracts: `43672`
- market_executable_contracts: `24597`
- snapshot_candidates: `24597`
- candidate_pool: `610`
- location_executable: `294`
- feasible: `220`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `159`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18862`
- MARKET_INELIGIBLE_SINGLETON: `6215`
- UNSAFE_OR_UNVERIFIED_LOCATION: `316`
- HIGHSEC_RESTRICTED_CAPITAL: `70`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `3`
