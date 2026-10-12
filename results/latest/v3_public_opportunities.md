# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T15:32:24.941Z
- Market snapshot: 2026-10-12T16:18:35.945Z
- Candidate universe: 24979; deep validation pool: 268; feasible: 196
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 158
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

- raw_contracts: `50744`
- eligible_contracts: `44274`
- market_executable_contracts: `24979`
- snapshot_candidates: `24979`
- candidate_pool: `611`
- location_executable: `268`
- feasible: `196`
- full_cash: `2`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `9`
- research_watch: `158`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `19070`
- MARKET_INELIGIBLE_SINGLETON: `6524`
- UNSAFE_OR_UNVERIFIED_LOCATION: `343`
- HIGHSEC_RESTRICTED_CAPITAL: `69`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_DATA_INCOMPLETE: `5`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
