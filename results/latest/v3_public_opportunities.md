# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T23:31:36.226Z
- Market snapshot: 2026-10-07T23:48:25.413Z
- Candidate universe: 24561; deep validation pool: 224; feasible: 162
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 142
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

- raw_contracts: `49964`
- eligible_contracts: `43376`
- market_executable_contracts: `24561`
- snapshot_candidates: `24561`
- candidate_pool: `605`
- location_executable: `224`
- feasible: `162`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `142`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18595`
- MARKET_INELIGIBLE_SINGLETON: `5994`
- UNSAFE_OR_UNVERIFIED_LOCATION: `381`
- HIGHSEC_RESTRICTED_CAPITAL: `56`
- FATAL_OR_ACCESS_UNVERIFIED: `11`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- NO_EXECUTABLE_ITEMS: `2`
