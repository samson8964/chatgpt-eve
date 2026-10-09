# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T15:31:26.824Z
- Market snapshot: 2026-10-09T15:18:37.479Z
- Candidate universe: 24412; deep validation pool: 269; feasible: 246
- FULL_CASH: 7
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 160
- FORMAL MAIL: 5

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
- eligible_contracts: `43540`
- market_executable_contracts: `24412`
- snapshot_candidates: `24412`
- candidate_pool: `610`
- location_executable: `269`
- feasible: `246`
- full_cash: `7`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `160`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18922`
- MARKET_INELIGIBLE_SINGLETON: `6188`
- UNSAFE_OR_UNVERIFIED_LOCATION: `341`
- HIGHSEC_RESTRICTED_CAPITAL: `18`
- FATAL_OR_ACCESS_UNVERIFIED: `16`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_TOO_SLOW: `6`
- SKIN_DOMINANT: `3`
- NO_EXECUTABLE_ITEMS: `2`
