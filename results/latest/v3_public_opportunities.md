# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T16:01:40.584Z
- Market snapshot: 2026-10-10T16:18:34.686Z
- Candidate universe: 24572; deep validation pool: 262; feasible: 183
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 3
- RESEARCH: 164
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

- raw_contracts: `50411`
- eligible_contracts: `43648`
- market_executable_contracts: `24572`
- snapshot_candidates: `24572`
- candidate_pool: `610`
- location_executable: `262`
- feasible: `183`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `3`
- research_watch: `164`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18856`
- MARKET_INELIGIBLE_SINGLETON: `6274`
- UNSAFE_OR_UNVERIFIED_LOCATION: `348`
- HIGHSEC_RESTRICTED_CAPITAL: `76`
- FATAL_OR_ACCESS_UNVERIFIED: `11`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_TOO_SLOW: `5`
- LIST_DATA_INCOMPLETE: `4`
- SKIN_DOMINANT: `3`
