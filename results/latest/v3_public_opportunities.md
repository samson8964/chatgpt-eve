# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T20:01:43.905Z
- Market snapshot: 2026-10-11T20:18:46.213Z
- Candidate universe: 24845; deep validation pool: 248; feasible: 175
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 160
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

- raw_contracts: `50685`
- eligible_contracts: `44033`
- market_executable_contracts: `24845`
- snapshot_candidates: `24845`
- candidate_pool: `611`
- location_executable: `248`
- feasible: `175`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `160`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18952`
- MARKET_INELIGIBLE_SINGLETON: `6419`
- UNSAFE_OR_UNVERIFIED_LOCATION: `363`
- HIGHSEC_RESTRICTED_CAPITAL: `71`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- LIST_DATA_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
- FATAL_OR_ACCESS_UNVERIFIED: `3`
- SKIN_DOMINANT: `2`
