# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T09:02:02.909Z
- Market snapshot: 2026-10-10T09:18:29.126Z
- Candidate universe: 24652; deep validation pool: 263; feasible: 192
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 13
- RESEARCH: 153
- FORMAL MAIL: 6

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
- eligible_contracts: `43726`
- market_executable_contracts: `24652`
- snapshot_candidates: `24652`
- candidate_pool: `610`
- location_executable: `263`
- feasible: `192`
- full_cash: `5`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `13`
- research_watch: `153`
- mail_eligible: `6`

## Rejection reasons

- BPC_ROUTED: `18857`
- MARKET_INELIGIBLE_SINGLETON: `6270`
- UNSAFE_OR_UNVERIFIED_LOCATION: `347`
- HIGHSEC_RESTRICTED_CAPITAL: `69`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_TOO_SLOW: `3`
- SKIN_DOMINANT: `2`
