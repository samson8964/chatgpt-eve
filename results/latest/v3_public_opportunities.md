# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T02:31:37.059Z
- Market snapshot: 2026-10-11T02:48:42.255Z
- Candidate universe: 24623; deep validation pool: 272; feasible: 196
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 156
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

- raw_contracts: `50208`
- eligible_contracts: `43659`
- market_executable_contracts: `24623`
- snapshot_candidates: `24623`
- candidate_pool: `610`
- location_executable: `272`
- feasible: `196`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `11`
- research_watch: `156`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18818`
- MARKET_INELIGIBLE_SINGLETON: `6207`
- UNSAFE_OR_UNVERIFIED_LOCATION: `338`
- HIGHSEC_RESTRICTED_CAPITAL: `72`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `3`
