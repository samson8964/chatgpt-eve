# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T08:01:38.125Z
- Market snapshot: 2026-10-09T07:48:26.097Z
- Candidate universe: 24219; deep validation pool: 246; feasible: 190
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 161
- FORMAL MAIL: 3

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50076`
- eligible_contracts: `43307`
- market_executable_contracts: `24219`
- snapshot_candidates: `24219`
- candidate_pool: `608`
- location_executable: `246`
- feasible: `190`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `161`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18865`
- MARKET_INELIGIBLE_SINGLETON: `6044`
- UNSAFE_OR_UNVERIFIED_LOCATION: `362`
- HIGHSEC_RESTRICTED_CAPITAL: `54`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `3`
- SKIN_DOMINANT: `2`
