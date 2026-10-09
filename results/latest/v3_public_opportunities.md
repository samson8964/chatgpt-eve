# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T03:31:38.732Z
- Market snapshot: 2026-10-09T03:48:19.907Z
- Candidate universe: 24331; deep validation pool: 276; feasible: 251
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 151
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

- raw_contracts: `50081`
- eligible_contracts: `43342`
- market_executable_contracts: `24331`
- snapshot_candidates: `24331`
- candidate_pool: `607`
- location_executable: `276`
- feasible: `251`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `11`
- research_watch: `151`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18794`
- MARKET_INELIGIBLE_SINGLETON: `6035`
- UNSAFE_OR_UNVERIFIED_LOCATION: `331`
- HIGHSEC_RESTRICTED_CAPITAL: `19`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- LIST_TOO_SLOW: `4`
- NO_EXECUTABLE_ITEMS: `3`
- SKIN_DOMINANT: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
