# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T01:01:49.705Z
- Market snapshot: 2026-10-08T00:48:48.211Z
- Candidate universe: 24551; deep validation pool: 230; feasible: 213
- FULL_CASH: 6
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 157
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

- raw_contracts: `49947`
- eligible_contracts: `43400`
- market_executable_contracts: `24551`
- snapshot_candidates: `24551`
- candidate_pool: `605`
- location_executable: `230`
- feasible: `213`
- full_cash: `6`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `5`
- research_watch: `157`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18625`
- MARKET_INELIGIBLE_SINGLETON: `5996`
- UNSAFE_OR_UNVERIFIED_LOCATION: `375`
- HIGHSEC_RESTRICTED_CAPITAL: `14`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
- LIST_DATA_INCOMPLETE: `2`
