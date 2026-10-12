# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T19:31:24.993Z
- Market snapshot: 2026-10-12T19:48:41.765Z
- Candidate universe: 25047; deep validation pool: 249; feasible: 173
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 160
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

- raw_contracts: `50767`
- eligible_contracts: `44321`
- market_executable_contracts: `25047`
- snapshot_candidates: `25047`
- candidate_pool: `611`
- location_executable: `249`
- feasible: `173`
- full_cash: `1`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `5`
- research_watch: `160`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `19045`
- MARKET_INELIGIBLE_SINGLETON: `6503`
- UNSAFE_OR_UNVERIFIED_LOCATION: `362`
- HIGHSEC_RESTRICTED_CAPITAL: `70`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- LIST_DATA_INCOMPLETE: `7`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `5`
- NO_EXECUTABLE_ITEMS: `1`
