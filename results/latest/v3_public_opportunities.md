# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T14:02:11.034Z
- Market snapshot: 2026-10-10T14:18:40.874Z
- Candidate universe: 24638; deep validation pool: 266; feasible: 180
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 158
- FORMAL MAIL: 0

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50292`
- eligible_contracts: `43766`
- market_executable_contracts: `24638`
- snapshot_candidates: `24638`
- candidate_pool: `610`
- location_executable: `266`
- feasible: `180`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `158`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18901`
- MARKET_INELIGIBLE_SINGLETON: `6271`
- UNSAFE_OR_UNVERIFIED_LOCATION: `344`
- HIGHSEC_RESTRICTED_CAPITAL: `82`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- FATAL_OR_ACCESS_UNVERIFIED: `3`
