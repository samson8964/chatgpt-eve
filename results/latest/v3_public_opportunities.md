# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T12:31:23.248Z
- Market snapshot: 2026-10-07T12:18:32.080Z
- Candidate universe: 24527; deep validation pool: 244; feasible: 179
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 3
- RESEARCH: 154
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

- raw_contracts: `49701`
- eligible_contracts: `43134`
- market_executable_contracts: `24527`
- snapshot_candidates: `24527`
- candidate_pool: `605`
- location_executable: `244`
- feasible: `179`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `3`
- research_watch: `154`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18380`
- MARKET_INELIGIBLE_SINGLETON: `5984`
- UNSAFE_OR_UNVERIFIED_LOCATION: `361`
- HIGHSEC_RESTRICTED_CAPITAL: `61`
- FATAL_OR_ACCESS_UNVERIFIED: `21`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
