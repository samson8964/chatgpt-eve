# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T12:31:26.608Z
- Market snapshot: 2026-10-08T12:18:39.320Z
- Candidate universe: 24556; deep validation pool: 235; feasible: 211
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 152
- FORMAL MAIL: 4

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `49913`
- eligible_contracts: `43354`
- market_executable_contracts: `24556`
- snapshot_candidates: `24556`
- candidate_pool: `606`
- location_executable: `235`
- feasible: `211`
- full_cash: `5`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `10`
- research_watch: `152`
- mail_eligible: `4`

## Rejection reasons

- BPC_ROUTED: `18571`
- MARKET_INELIGIBLE_SINGLETON: `6015`
- UNSAFE_OR_UNVERIFIED_LOCATION: `371`
- HIGHSEC_RESTRICTED_CAPITAL: `20`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- SKIN_DOMINANT: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
- LIST_TOO_SLOW: `2`
- LIST_DATA_INCOMPLETE: `2`
