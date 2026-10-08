# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T10:31:24.002Z
- Market snapshot: 2026-10-08T10:18:34.833Z
- Candidate universe: 24598; deep validation pool: 230; feasible: 167
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 149
- FORMAL MAIL: 1

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `49878`
- eligible_contracts: `43371`
- market_executable_contracts: `24598`
- snapshot_candidates: `24598`
- candidate_pool: `605`
- location_executable: `230`
- feasible: `167`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `10`
- research_watch: `149`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18544`
- MARKET_INELIGIBLE_SINGLETON: `6015`
- UNSAFE_OR_UNVERIFIED_LOCATION: `375`
- HIGHSEC_RESTRICTED_CAPITAL: `60`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- LIST_DATA_INCOMPLETE: `5`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
