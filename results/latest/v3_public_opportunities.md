# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T05:31:41.612Z
- Market snapshot: 2026-10-08T05:18:28.463Z
- Candidate universe: 24563; deep validation pool: 242; feasible: 222
- FULL_CASH: 6
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 152
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

- raw_contracts: `49866`
- eligible_contracts: `43322`
- market_executable_contracts: `24563`
- snapshot_candidates: `24563`
- candidate_pool: `605`
- location_executable: `242`
- feasible: `222`
- full_cash: `6`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `10`
- research_watch: `152`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18532`
- MARKET_INELIGIBLE_SINGLETON: `5997`
- UNSAFE_OR_UNVERIFIED_LOCATION: `363`
- HIGHSEC_RESTRICTED_CAPITAL: `17`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
- LIST_DATA_INCOMPLETE: `2`
