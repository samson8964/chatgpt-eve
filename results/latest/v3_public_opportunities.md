# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T18:01:29.270Z
- Market snapshot: 2026-10-08T17:48:45.502Z
- Candidate universe: 24425; deep validation pool: 277; feasible: 201
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 2
- RESEARCH: 160
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

- raw_contracts: `50119`
- eligible_contracts: `43455`
- market_executable_contracts: `24425`
- snapshot_candidates: `24425`
- candidate_pool: `607`
- location_executable: `277`
- feasible: `201`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `2`
- research_watch: `160`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18804`
- MARKET_INELIGIBLE_SINGLETON: `6111`
- UNSAFE_OR_UNVERIFIED_LOCATION: `330`
- HIGHSEC_RESTRICTED_CAPITAL: `72`
- FATAL_OR_ACCESS_UNVERIFIED: `20`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
