# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T10:01:36.309Z
- Market snapshot: 2026-10-10T10:18:30.980Z
- Candidate universe: 24621; deep validation pool: 269; feasible: 245
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 160
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

- raw_contracts: `50403`
- eligible_contracts: `43696`
- market_executable_contracts: `24621`
- snapshot_candidates: `24621`
- candidate_pool: `610`
- location_executable: `269`
- feasible: `245`
- full_cash: `5`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `7`
- research_watch: `160`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18861`
- MARKET_INELIGIBLE_SINGLETON: `6270`
- UNSAFE_OR_UNVERIFIED_LOCATION: `341`
- HIGHSEC_RESTRICTED_CAPITAL: `18`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- NO_EXECUTABLE_ITEMS: `2`
