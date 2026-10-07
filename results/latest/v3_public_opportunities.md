# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T19:01:39.374Z
- Market snapshot: 2026-10-07T18:48:49.968Z
- Candidate universe: 24544; deep validation pool: 228; feasible: 160
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 146
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

- raw_contracts: `49791`
- eligible_contracts: `43292`
- market_executable_contracts: `24544`
- snapshot_candidates: `24544`
- candidate_pool: `605`
- location_executable: `228`
- feasible: `160`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `146`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18530`
- MARKET_INELIGIBLE_SINGLETON: `5985`
- UNSAFE_OR_UNVERIFIED_LOCATION: `377`
- HIGHSEC_RESTRICTED_CAPITAL: `62`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- LIST_DATA_INCOMPLETE: `5`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- NO_EXECUTABLE_ITEMS: `2`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
