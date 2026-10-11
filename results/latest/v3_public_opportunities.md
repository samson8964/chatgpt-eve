# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T20:31:45.524Z
- Market snapshot: 2026-10-11T20:48:43.307Z
- Candidate universe: 24849; deep validation pool: 262; feasible: 184
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 161
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

- raw_contracts: `50698`
- eligible_contracts: `44051`
- market_executable_contracts: `24849`
- snapshot_candidates: `24849`
- candidate_pool: `611`
- location_executable: `262`
- feasible: `184`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `161`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18968`
- MARKET_INELIGIBLE_SINGLETON: `6410`
- UNSAFE_OR_UNVERIFIED_LOCATION: `349`
- HIGHSEC_RESTRICTED_CAPITAL: `72`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `6`
- LIST_TOO_SLOW: `3`
- FATAL_OR_ACCESS_UNVERIFIED: `1`
