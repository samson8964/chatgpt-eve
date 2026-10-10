# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T17:01:26.415Z
- Market snapshot: 2026-10-10T17:18:37.764Z
- Candidate universe: 24719; deep validation pool: 280; feasible: 202
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 160
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

- raw_contracts: `50446`
- eligible_contracts: `43714`
- market_executable_contracts: `24719`
- snapshot_candidates: `24719`
- candidate_pool: `610`
- location_executable: `280`
- feasible: `202`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `160`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18769`
- MARKET_INELIGIBLE_SINGLETON: `6317`
- UNSAFE_OR_UNVERIFIED_LOCATION: `330`
- HIGHSEC_RESTRICTED_CAPITAL: `72`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- SKIN_DOMINANT: `5`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `4`
- NO_EXECUTABLE_ITEMS: `1`
