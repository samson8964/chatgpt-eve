# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T16:01:25.210Z
- Market snapshot: 2026-10-09T15:48:36.299Z
- Candidate universe: 24392; deep validation pool: 275; feasible: 204
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 158
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

- raw_contracts: `50200`
- eligible_contracts: `43533`
- market_executable_contracts: `24392`
- snapshot_candidates: `24392`
- candidate_pool: `610`
- location_executable: `275`
- feasible: `204`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `158`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18931`
- MARKET_INELIGIBLE_SINGLETON: `6187`
- UNSAFE_OR_UNVERIFIED_LOCATION: `335`
- HIGHSEC_RESTRICTED_CAPITAL: `69`
- FATAL_OR_ACCESS_UNVERIFIED: `17`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `2`
