# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T00:01:33.647Z
- Market snapshot: 2026-10-09T00:18:23.722Z
- Candidate universe: 24340; deep validation pool: 247; feasible: 194
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 156
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

- raw_contracts: `50103`
- eligible_contracts: `43441`
- market_executable_contracts: `24340`
- snapshot_candidates: `24340`
- candidate_pool: `607`
- location_executable: `247`
- feasible: `194`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `156`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18877`
- MARKET_INELIGIBLE_SINGLETON: `6039`
- UNSAFE_OR_UNVERIFIED_LOCATION: `360`
- HIGHSEC_RESTRICTED_CAPITAL: `51`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- LIST_TOO_SLOW: `3`
- LIST_DATA_INCOMPLETE: `3`
- SKIN_DOMINANT: `2`
