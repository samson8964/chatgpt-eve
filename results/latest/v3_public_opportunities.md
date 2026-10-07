# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T20:31:56.089Z
- Market snapshot: 2026-10-07T20:48:25.478Z
- Candidate universe: 24541; deep validation pool: 217; feasible: 163
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 145
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

- raw_contracts: `49935`
- eligible_contracts: `43363`
- market_executable_contracts: `24541`
- snapshot_candidates: `24541`
- candidate_pool: `605`
- location_executable: `217`
- feasible: `163`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `145`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18602`
- MARKET_INELIGIBLE_SINGLETON: `6000`
- UNSAFE_OR_UNVERIFIED_LOCATION: `388`
- HIGHSEC_RESTRICTED_CAPITAL: `50`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- SKIN_DOMINANT: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
