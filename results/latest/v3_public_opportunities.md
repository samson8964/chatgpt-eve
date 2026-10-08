# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T20:01:21.948Z
- Market snapshot: 2026-10-08T18:48:53.568Z
- Candidate universe: 24410; deep validation pool: 252; feasible: 182
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 157
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

- raw_contracts: `50161`
- eligible_contracts: `43473`
- market_executable_contracts: `24410`
- snapshot_candidates: `24410`
- candidate_pool: `607`
- location_executable: `252`
- feasible: `182`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `5`
- research_watch: `157`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18839`
- MARKET_INELIGIBLE_SINGLETON: `6099`
- UNSAFE_OR_UNVERIFIED_LOCATION: `355`
- HIGHSEC_RESTRICTED_CAPITAL: `66`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `3`
- LIST_DATA_INCOMPLETE: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
