# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T09:31:23.353Z
- Market snapshot: 2026-10-08T09:18:30.384Z
- Candidate universe: 24604; deep validation pool: 232; feasible: 162
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 141
- FORMAL MAIL: 3

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `49894`
- eligible_contracts: `43369`
- market_executable_contracts: `24604`
- snapshot_candidates: `24604`
- candidate_pool: `605`
- location_executable: `232`
- feasible: `162`
- full_cash: `4`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `11`
- research_watch: `141`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18537`
- MARKET_INELIGIBLE_SINGLETON: `6011`
- UNSAFE_OR_UNVERIFIED_LOCATION: `373`
- HIGHSEC_RESTRICTED_CAPITAL: `67`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- SKIN_DOMINANT: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
