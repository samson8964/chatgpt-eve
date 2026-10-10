# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T10:01:36.309Z
- Market snapshot: 2026-10-10T09:48:32.338Z
- Candidate universe: 24629; deep validation pool: 262; feasible: 186
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 160
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

- raw_contracts: `50403`
- eligible_contracts: `43709`
- market_executable_contracts: `24629`
- snapshot_candidates: `24629`
- candidate_pool: `611`
- location_executable: `262`
- feasible: `186`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `160`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18863`
- MARKET_INELIGIBLE_SINGLETON: `6269`
- UNSAFE_OR_UNVERIFIED_LOCATION: `349`
- HIGHSEC_RESTRICTED_CAPITAL: `70`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- NO_EXECUTABLE_ITEMS: `2`
