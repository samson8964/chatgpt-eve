# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T03:01:28.368Z
- Market snapshot: 2026-10-09T03:18:16.746Z
- Candidate universe: 24338; deep validation pool: 268; feasible: 201
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 155
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

- raw_contracts: `50087`
- eligible_contracts: `43342`
- market_executable_contracts: `24338`
- snapshot_candidates: `24338`
- candidate_pool: `607`
- location_executable: `268`
- feasible: `201`
- full_cash: `2`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `8`
- research_watch: `155`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18784`
- MARKET_INELIGIBLE_SINGLETON: `6041`
- UNSAFE_OR_UNVERIFIED_LOCATION: `339`
- HIGHSEC_RESTRICTED_CAPITAL: `62`
- FATAL_OR_ACCESS_UNVERIFIED: `11`
- SKIN_DOMINANT: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
- NO_EXECUTABLE_ITEMS: `2`
