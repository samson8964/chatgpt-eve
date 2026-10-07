# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T07:31:21.214Z
- Market snapshot: 2026-10-07T07:18:19.726Z
- Candidate universe: 24575; deep validation pool: 237; feasible: 165
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 3
- RESEARCH: 158
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

- raw_contracts: `49672`
- eligible_contracts: `43175`
- market_executable_contracts: `24575`
- snapshot_candidates: `24575`
- candidate_pool: `605`
- location_executable: `237`
- feasible: `165`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `3`
- research_watch: `158`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18374`
- MARKET_INELIGIBLE_SINGLETON: `5999`
- UNSAFE_OR_UNVERIFIED_LOCATION: `368`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- LIST_UNSUPPORTED: `15`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- FATAL_OR_ACCESS_UNVERIFIED: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
