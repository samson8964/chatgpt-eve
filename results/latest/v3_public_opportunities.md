# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T01:31:36.380Z
- Market snapshot: 2026-10-08T01:18:21.885Z
- Candidate universe: 24563; deep validation pool: 236; feasible: 170
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 151
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

- raw_contracts: `49957`
- eligible_contracts: `43422`
- market_executable_contracts: `24563`
- snapshot_candidates: `24563`
- candidate_pool: `605`
- location_executable: `236`
- feasible: `170`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `151`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18637`
- MARKET_INELIGIBLE_SINGLETON: `5995`
- UNSAFE_OR_UNVERIFIED_LOCATION: `369`
- HIGHSEC_RESTRICTED_CAPITAL: `62`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
