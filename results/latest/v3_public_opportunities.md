# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T01:02:40.495Z
- Market snapshot: 2026-10-09T00:48:53.268Z
- Candidate universe: 24318; deep validation pool: 244; feasible: 189
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 155
- FORMAL MAIL: 4

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50092`
- eligible_contracts: `43400`
- market_executable_contracts: `24318`
- snapshot_candidates: `24318`
- candidate_pool: `607`
- location_executable: `244`
- feasible: `189`
- full_cash: `4`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `10`
- research_watch: `155`
- mail_eligible: `4`

## Rejection reasons

- BPC_ROUTED: `18861`
- MARKET_INELIGIBLE_SINGLETON: `6012`
- UNSAFE_OR_UNVERIFIED_LOCATION: `363`
- HIGHSEC_RESTRICTED_CAPITAL: `50`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- BARTER_PROCUREMENT_INCOMPLETE: `5`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
- LIST_DATA_INCOMPLETE: `3`
- NO_EXECUTABLE_ITEMS: `2`
