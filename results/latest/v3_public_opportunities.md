# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T06:31:28.810Z
- Market snapshot: 2026-10-09T06:18:24.186Z
- Candidate universe: 24209; deep validation pool: 239; feasible: 179
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 150
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

- raw_contracts: `50070`
- eligible_contracts: `43247`
- market_executable_contracts: `24209`
- snapshot_candidates: `24209`
- candidate_pool: `607`
- location_executable: `239`
- feasible: `179`
- full_cash: `5`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `11`
- research_watch: `150`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18817`
- MARKET_INELIGIBLE_SINGLETON: `6045`
- UNSAFE_OR_UNVERIFIED_LOCATION: `368`
- HIGHSEC_RESTRICTED_CAPITAL: `58`
- FATAL_OR_ACCESS_UNVERIFIED: `13`
- LIST_DATA_INCOMPLETE: `5`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- LIST_TOO_SLOW: `3`
- SKIN_DOMINANT: `2`
