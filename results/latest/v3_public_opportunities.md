# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T08:31:43.331Z
- Market snapshot: 2026-10-09T08:48:35.054Z
- Candidate universe: 24201; deep validation pool: 254; feasible: 190
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 157
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

- raw_contracts: `50080`
- eligible_contracts: `43302`
- market_executable_contracts: `24201`
- snapshot_candidates: `24201`
- candidate_pool: `608`
- location_executable: `254`
- feasible: `190`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `157`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18881`
- MARKET_INELIGIBLE_SINGLETON: `6044`
- UNSAFE_OR_UNVERIFIED_LOCATION: `354`
- HIGHSEC_RESTRICTED_CAPITAL: `61`
- FATAL_OR_ACCESS_UNVERIFIED: `14`
- BARTER_PROCUREMENT_INCOMPLETE: `5`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
- LIST_DATA_INCOMPLETE: `3`
