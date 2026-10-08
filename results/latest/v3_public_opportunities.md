# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T07:31:48.240Z
- Market snapshot: 2026-10-08T07:18:29.843Z
- Candidate universe: 24560; deep validation pool: 227; feasible: 219
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 13
- RESEARCH: 151
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

- raw_contracts: `49929`
- eligible_contracts: `43377`
- market_executable_contracts: `24560`
- snapshot_candidates: `24560`
- candidate_pool: `605`
- location_executable: `227`
- feasible: `219`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `13`
- research_watch: `151`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18591`
- MARKET_INELIGIBLE_SINGLETON: `5989`
- UNSAFE_OR_UNVERIFIED_LOCATION: `378`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- HIGHSEC_RESTRICTED_CAPITAL: `5`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
- LIST_DATA_INCOMPLETE: `2`
