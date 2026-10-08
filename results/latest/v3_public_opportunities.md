# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T22:01:42.235Z
- Market snapshot: 2026-10-08T22:18:28.029Z
- Candidate universe: 24390; deep validation pool: 248; feasible: 230
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 154
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

- raw_contracts: `50126`
- eligible_contracts: `43444`
- market_executable_contracts: `24390`
- snapshot_candidates: `24390`
- candidate_pool: `607`
- location_executable: `248`
- feasible: `230`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `154`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18837`
- MARKET_INELIGIBLE_SINGLETON: `6068`
- UNSAFE_OR_UNVERIFIED_LOCATION: `359`
- HIGHSEC_RESTRICTED_CAPITAL: `15`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
- LIST_DATA_INCOMPLETE: `2`
