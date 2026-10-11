# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T02:01:37.463Z
- Market snapshot: 2026-10-11T02:18:35.241Z
- Candidate universe: 24623; deep validation pool: 268; feasible: 190
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 161
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

- raw_contracts: `50247`
- eligible_contracts: `43663`
- market_executable_contracts: `24623`
- snapshot_candidates: `24623`
- candidate_pool: `610`
- location_executable: `268`
- feasible: `190`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `161`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18819`
- MARKET_INELIGIBLE_SINGLETON: `6215`
- UNSAFE_OR_UNVERIFIED_LOCATION: `342`
- HIGHSEC_RESTRICTED_CAPITAL: `73`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `5`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `3`
