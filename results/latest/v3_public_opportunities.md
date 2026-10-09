# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T14:01:24.919Z
- Market snapshot: 2026-10-09T14:18:35.463Z
- Candidate universe: 24403; deep validation pool: 237; feasible: 166
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 147
- FORMAL MAIL: 4

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50260`
- eligible_contracts: `43574`
- market_executable_contracts: `24403`
- snapshot_candidates: `24403`
- candidate_pool: `610`
- location_executable: `237`
- feasible: `166`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `147`
- mail_eligible: `4`

## Rejection reasons

- BPC_ROUTED: `18956`
- MARKET_INELIGIBLE_SINGLETON: `6212`
- UNSAFE_OR_UNVERIFIED_LOCATION: `373`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_DATA_INCOMPLETE: `5`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
