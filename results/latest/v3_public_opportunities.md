# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T18:31:23.350Z
- Market snapshot: 2026-10-07T18:48:49.968Z
- Candidate universe: 24530; deep validation pool: 217; feasible: 152
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 137
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

- raw_contracts: `49687`
- eligible_contracts: `43196`
- market_executable_contracts: `24530`
- snapshot_candidates: `24530`
- candidate_pool: `605`
- location_executable: `217`
- feasible: `152`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `5`
- research_watch: `137`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18446`
- MARKET_INELIGIBLE_SINGLETON: `5993`
- UNSAFE_OR_UNVERIFIED_LOCATION: `388`
- HIGHSEC_RESTRICTED_CAPITAL: `61`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_DATA_INCOMPLETE: `3`
