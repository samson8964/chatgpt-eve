# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T11:09:42.027Z
- Market snapshot: 2026-10-08T10:48:48.655Z
- Candidate universe: 24598; deep validation pool: 234; feasible: 167
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 148
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

- raw_contracts: `49923`
- eligible_contracts: `43403`
- market_executable_contracts: `24598`
- snapshot_candidates: `24598`
- candidate_pool: `605`
- location_executable: `234`
- feasible: `167`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `148`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18578`
- MARKET_INELIGIBLE_SINGLETON: `6015`
- UNSAFE_OR_UNVERIFIED_LOCATION: `371`
- HIGHSEC_RESTRICTED_CAPITAL: `65`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- LIST_DATA_INCOMPLETE: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
- SKIN_DOMINANT: `2`
