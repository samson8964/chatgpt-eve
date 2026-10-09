# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T04:01:36.053Z
- Market snapshot: 2026-10-09T03:48:19.907Z
- Candidate universe: 24310; deep validation pool: 280; feasible: 207
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 156
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

- raw_contracts: `50083`
- eligible_contracts: `43353`
- market_executable_contracts: `24310`
- snapshot_candidates: `24310`
- candidate_pool: `607`
- location_executable: `280`
- feasible: `207`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `156`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18820`
- MARKET_INELIGIBLE_SINGLETON: `6028`
- UNSAFE_OR_UNVERIFIED_LOCATION: `327`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- SKIN_DOMINANT: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
- NO_EXECUTABLE_ITEMS: `1`
