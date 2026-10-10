# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T00:31:41.588Z
- Market snapshot: 2026-10-10T00:48:50.050Z
- Candidate universe: 24629; deep validation pool: 298; feasible: 228
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 161
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

- raw_contracts: `50375`
- eligible_contracts: `43721`
- market_executable_contracts: `24629`
- snapshot_candidates: `24629`
- candidate_pool: `610`
- location_executable: `298`
- feasible: `228`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `161`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18882`
- MARKET_INELIGIBLE_SINGLETON: `6237`
- UNSAFE_OR_UNVERIFIED_LOCATION: `312`
- HIGHSEC_RESTRICTED_CAPITAL: `63`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- SKIN_DOMINANT: `7`
- FATAL_OR_ACCESS_UNVERIFIED: `3`
- LIST_TOO_SLOW: `3`
