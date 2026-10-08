# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T23:01:42.554Z
- Market snapshot: 2026-10-08T23:18:30.316Z
- Candidate universe: 24391; deep validation pool: 241; feasible: 169
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
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

- raw_contracts: `50112`
- eligible_contracts: `43456`
- market_executable_contracts: `24391`
- snapshot_candidates: `24391`
- candidate_pool: `607`
- location_executable: `241`
- feasible: `169`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `154`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18840`
- MARKET_INELIGIBLE_SINGLETON: `6055`
- UNSAFE_OR_UNVERIFIED_LOCATION: `366`
- HIGHSEC_RESTRICTED_CAPITAL: `69`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- LIST_DATA_INCOMPLETE: `5`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
