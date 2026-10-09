# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T09:31:22.936Z
- Market snapshot: 2026-10-09T09:18:33.664Z
- Candidate universe: 24191; deep validation pool: 271; feasible: 213
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 163
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

- raw_contracts: `50079`
- eligible_contracts: `43356`
- market_executable_contracts: `24191`
- snapshot_candidates: `24191`
- candidate_pool: `610`
- location_executable: `271`
- feasible: `213`
- full_cash: `1`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `5`
- research_watch: `163`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18943`
- MARKET_INELIGIBLE_SINGLETON: `6049`
- UNSAFE_OR_UNVERIFIED_LOCATION: `339`
- HIGHSEC_RESTRICTED_CAPITAL: `55`
- FATAL_OR_ACCESS_UNVERIFIED: `18`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
