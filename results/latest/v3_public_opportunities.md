# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T07:31:41.377Z
- Market snapshot: 2026-10-09T07:18:29.587Z
- Candidate universe: 24207; deep validation pool: 246; feasible: 179
- FULL_CASH: 7
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 150
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

- raw_contracts: `50084`
- eligible_contracts: `43291`
- market_executable_contracts: `24207`
- snapshot_candidates: `24207`
- candidate_pool: `607`
- location_executable: `246`
- feasible: `179`
- full_cash: `7`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `11`
- research_watch: `150`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18863`
- MARKET_INELIGIBLE_SINGLETON: `6044`
- UNSAFE_OR_UNVERIFIED_LOCATION: `361`
- HIGHSEC_RESTRICTED_CAPITAL: `64`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_DATA_INCOMPLETE: `5`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
