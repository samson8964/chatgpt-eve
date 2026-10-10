# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T10:31:43.523Z
- Market snapshot: 2026-10-10T10:48:31.826Z
- Candidate universe: 24631; deep validation pool: 267; feasible: 196
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 10
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

- raw_contracts: `50380`
- eligible_contracts: `43702`
- market_executable_contracts: `24631`
- snapshot_candidates: `24631`
- candidate_pool: `610`
- location_executable: `267`
- feasible: `196`
- full_cash: `5`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `10`
- research_watch: `157`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18858`
- MARKET_INELIGIBLE_SINGLETON: `6262`
- UNSAFE_OR_UNVERIFIED_LOCATION: `343`
- HIGHSEC_RESTRICTED_CAPITAL: `69`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `2`
