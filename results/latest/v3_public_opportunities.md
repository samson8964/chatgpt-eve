# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T11:31:50.731Z
- Market snapshot: 2026-10-09T11:48:37.421Z
- Candidate universe: 24389; deep validation pool: 230; feasible: 173
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 155
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

- raw_contracts: `50243`
- eligible_contracts: `43527`
- market_executable_contracts: `24389`
- snapshot_candidates: `24389`
- candidate_pool: `610`
- location_executable: `230`
- feasible: `173`
- full_cash: `1`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `11`
- research_watch: `155`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18918`
- MARKET_INELIGIBLE_SINGLETON: `6231`
- UNSAFE_OR_UNVERIFIED_LOCATION: `380`
- HIGHSEC_RESTRICTED_CAPITAL: `53`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- LIST_DATA_INCOMPLETE: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
