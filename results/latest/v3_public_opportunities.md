# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T19:31:27.097Z
- Market snapshot: 2026-10-09T19:18:31.907Z
- Candidate universe: 24522; deep validation pool: 249; feasible: 178
- FULL_CASH: 8
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 154
- FORMAL MAIL: 5

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50240`
- eligible_contracts: `43592`
- market_executable_contracts: `24522`
- snapshot_candidates: `24522`
- candidate_pool: `610`
- location_executable: `249`
- feasible: `178`
- full_cash: `8`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `9`
- research_watch: `154`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18860`
- MARKET_INELIGIBLE_SINGLETON: `6182`
- UNSAFE_OR_UNVERIFIED_LOCATION: `361`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- LIST_TOO_SLOW: `6`
- LIST_DATA_INCOMPLETE: `6`
- SKIN_DOMINANT: `3`
