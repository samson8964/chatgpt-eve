# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T21:31:40.502Z
- Market snapshot: 2026-10-07T21:18:23.330Z
- Candidate universe: 24537; deep validation pool: 225; feasible: 157
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 145
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

- raw_contracts: `49950`
- eligible_contracts: `43373`
- market_executable_contracts: `24537`
- snapshot_candidates: `24537`
- candidate_pool: `605`
- location_executable: `225`
- feasible: `157`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `145`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18616`
- MARKET_INELIGIBLE_SINGLETON: `6001`
- UNSAFE_OR_UNVERIFIED_LOCATION: `380`
- HIGHSEC_RESTRICTED_CAPITAL: `62`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- NO_EXECUTABLE_ITEMS: `2`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
