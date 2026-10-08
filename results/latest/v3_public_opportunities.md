# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T09:31:23.353Z
- Market snapshot: 2026-10-08T09:48:30.368Z
- Candidate universe: 24590; deep validation pool: 242; feasible: 186
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
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

- raw_contracts: `49894`
- eligible_contracts: `43343`
- market_executable_contracts: `24590`
- snapshot_candidates: `24590`
- candidate_pool: `605`
- location_executable: `242`
- feasible: `186`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `156`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18522`
- MARKET_INELIGIBLE_SINGLETON: `6010`
- UNSAFE_OR_UNVERIFIED_LOCATION: `363`
- HIGHSEC_RESTRICTED_CAPITAL: `53`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `5`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
- LIST_DATA_INCOMPLETE: `2`
