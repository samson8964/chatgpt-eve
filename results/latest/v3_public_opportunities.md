# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T05:01:38.959Z
- Market snapshot: 2026-10-08T05:18:28.463Z
- Candidate universe: 24547; deep validation pool: 252; feasible: 246
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 157
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

- raw_contracts: `49845`
- eligible_contracts: `43310`
- market_executable_contracts: `24547`
- snapshot_candidates: `24547`
- candidate_pool: `605`
- location_executable: `252`
- feasible: `246`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `157`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18540`
- MARKET_INELIGIBLE_SINGLETON: `5990`
- UNSAFE_OR_UNVERIFIED_LOCATION: `353`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- HIGHSEC_RESTRICTED_CAPITAL: `5`
- BARTER_PROCUREMENT_INCOMPLETE: `5`
- LIST_TOO_SLOW: `3`
- SKIN_DOMINANT: `1`
