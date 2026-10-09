# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T03:31:38.732Z
- Market snapshot: 2026-10-09T03:18:16.746Z
- Candidate universe: 24332; deep validation pool: 273; feasible: 202
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 155
- FORMAL MAIL: 5

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50081`
- eligible_contracts: `43344`
- market_executable_contracts: `24332`
- snapshot_candidates: `24332`
- candidate_pool: `607`
- location_executable: `273`
- feasible: `202`
- full_cash: `5`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `155`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18795`
- MARKET_INELIGIBLE_SINGLETON: `6037`
- UNSAFE_OR_UNVERIFIED_LOCATION: `334`
- HIGHSEC_RESTRICTED_CAPITAL: `65`
- FATAL_OR_ACCESS_UNVERIFIED: `12`
- SKIN_DOMINANT: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
- NO_EXECUTABLE_ITEMS: `2`
