# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T21:31:40.502Z
- Market snapshot: 2026-10-07T21:18:23.330Z
- Candidate universe: 24524; deep validation pool: 219; feasible: 201
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 156
- FORMAL MAIL: 2

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `49925`
- eligible_contracts: `43373`
- market_executable_contracts: `24524`
- snapshot_candidates: `24524`
- candidate_pool: `605`
- location_executable: `219`
- feasible: `201`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `156`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18626`
- MARKET_INELIGIBLE_SINGLETON: `6003`
- UNSAFE_OR_UNVERIFIED_LOCATION: `386`
- HIGHSEC_RESTRICTED_CAPITAL: `14`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- SKIN_DOMINANT: `4`
- LIST_DATA_INCOMPLETE: `4`
- LIST_TOO_SLOW: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
