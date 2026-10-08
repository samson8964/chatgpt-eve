# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T14:01:23.153Z
- Market snapshot: 2026-10-08T13:48:32.995Z
- Candidate universe: 24571; deep validation pool: 228; feasible: 164
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 142
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

- raw_contracts: `50045`
- eligible_contracts: `43469`
- market_executable_contracts: `24571`
- snapshot_candidates: `24571`
- candidate_pool: `606`
- location_executable: `228`
- feasible: `164`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `10`
- research_watch: `142`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18673`
- MARKET_INELIGIBLE_SINGLETON: `6070`
- UNSAFE_OR_UNVERIFIED_LOCATION: `378`
- HIGHSEC_RESTRICTED_CAPITAL: `61`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- LIST_DATA_INCOMPLETE: `5`
- SKIN_DOMINANT: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
