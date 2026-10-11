# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T13:01:44.081Z
- Market snapshot: 2026-10-11T13:18:46.964Z
- Candidate universe: 24503; deep validation pool: 260; feasible: 182
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 163
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

- raw_contracts: `50291`
- eligible_contracts: `43739`
- market_executable_contracts: `24503`
- snapshot_candidates: `24503`
- candidate_pool: `610`
- location_executable: `260`
- feasible: `182`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `163`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `19009`
- MARKET_INELIGIBLE_SINGLETON: `6216`
- UNSAFE_OR_UNVERIFIED_LOCATION: `350`
- HIGHSEC_RESTRICTED_CAPITAL: `71`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- SKIN_DOMINANT: `7`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_TOO_SLOW: `5`
- LIST_DATA_INCOMPLETE: `4`
