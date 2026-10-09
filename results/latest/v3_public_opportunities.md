# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T22:31:36.279Z
- Market snapshot: 2026-10-09T22:18:28.942Z
- Candidate universe: 24593; deep validation pool: 257; feasible: 181
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 158
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

- raw_contracts: `50318`
- eligible_contracts: `43651`
- market_executable_contracts: `24593`
- snapshot_candidates: `24593`
- candidate_pool: `610`
- location_executable: `257`
- feasible: `181`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `158`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18847`
- MARKET_INELIGIBLE_SINGLETON: `6203`
- UNSAFE_OR_UNVERIFIED_LOCATION: `353`
- HIGHSEC_RESTRICTED_CAPITAL: `72`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- SKIN_DOMINANT: `4`
- FATAL_OR_ACCESS_UNVERIFIED: `4`
- LIST_TOO_SLOW: `3`
- LIST_DATA_INCOMPLETE: `1`
