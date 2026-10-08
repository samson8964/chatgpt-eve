# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T08:01:41.046Z
- Market snapshot: 2026-10-08T07:48:33.970Z
- Candidate universe: 24559; deep validation pool: 230; feasible: 213
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 153
- FORMAL MAIL: 4

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `49868`
- eligible_contracts: `43343`
- market_executable_contracts: `24559`
- snapshot_candidates: `24559`
- candidate_pool: `605`
- location_executable: `230`
- feasible: `213`
- full_cash: `5`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `9`
- research_watch: `153`
- mail_eligible: `4`

## Rejection reasons

- BPC_ROUTED: `18563`
- MARKET_INELIGIBLE_SINGLETON: `5981`
- UNSAFE_OR_UNVERIFIED_LOCATION: `375`
- HIGHSEC_RESTRICTED_CAPITAL: `12`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
- LIST_DATA_INCOMPLETE: `3`
- NO_EXECUTABLE_ITEMS: `2`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
