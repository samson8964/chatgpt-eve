# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T14:31:41.694Z
- Market snapshot: 2026-10-09T14:18:35.463Z
- Candidate universe: 24429; deep validation pool: 242; feasible: 174
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 7
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

- raw_contracts: `50233`
- eligible_contracts: `43557`
- market_executable_contracts: `24429`
- snapshot_candidates: `24429`
- candidate_pool: `610`
- location_executable: `242`
- feasible: `174`
- full_cash: `4`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `7`
- research_watch: `151`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18912`
- MARKET_INELIGIBLE_SINGLETON: `6203`
- UNSAFE_OR_UNVERIFIED_LOCATION: `368`
- HIGHSEC_RESTRICTED_CAPITAL: `62`
- FATAL_OR_ACCESS_UNVERIFIED: `11`
- BARTER_PROCUREMENT_INCOMPLETE: `9`
- LIST_DATA_INCOMPLETE: `5`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- NO_EXECUTABLE_ITEMS: `2`
