# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T21:31:59.995Z
- Market snapshot: 2026-10-08T21:48:28.672Z
- Candidate universe: 24392; deep validation pool: 244; feasible: 188
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 159
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

- raw_contracts: `50136`
- eligible_contracts: `43449`
- market_executable_contracts: `24392`
- snapshot_candidates: `24392`
- candidate_pool: `607`
- location_executable: `244`
- feasible: `188`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `159`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18837`
- MARKET_INELIGIBLE_SINGLETON: `6070`
- UNSAFE_OR_UNVERIFIED_LOCATION: `363`
- HIGHSEC_RESTRICTED_CAPITAL: `54`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- BARTER_PROCUREMENT_INCOMPLETE: `5`
- LIST_DATA_INCOMPLETE: `4`
- LIST_TOO_SLOW: `3`
- SKIN_DOMINANT: `2`
