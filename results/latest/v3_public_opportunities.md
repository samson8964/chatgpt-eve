# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T21:31:43.427Z
- Market snapshot: 2026-10-09T21:18:30.842Z
- Candidate universe: 24602; deep validation pool: 298; feasible: 225
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 162
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

- raw_contracts: `50338`
- eligible_contracts: `43679`
- market_executable_contracts: `24602`
- snapshot_candidates: `24602`
- candidate_pool: `610`
- location_executable: `298`
- feasible: `225`
- full_cash: `4`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `5`
- research_watch: `162`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18865`
- MARKET_INELIGIBLE_SINGLETON: `6219`
- UNSAFE_OR_UNVERIFIED_LOCATION: `312`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
- NO_EXECUTABLE_ITEMS: `2`
