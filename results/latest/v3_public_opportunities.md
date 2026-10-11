# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T21:01:37.253Z
- Market snapshot: 2026-10-11T21:18:42.256Z
- Candidate universe: 24859; deep validation pool: 259; feasible: 183
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 10
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

- raw_contracts: `50691`
- eligible_contracts: `44058`
- market_executable_contracts: `24859`
- snapshot_candidates: `24859`
- candidate_pool: `611`
- location_executable: `259`
- feasible: `183`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `10`
- research_watch: `157`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18965`
- MARKET_INELIGIBLE_SINGLETON: `6416`
- UNSAFE_OR_UNVERIFIED_LOCATION: `352`
- HIGHSEC_RESTRICTED_CAPITAL: `73`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
- LIST_DATA_INCOMPLETE: `3`
