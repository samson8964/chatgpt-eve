# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T21:01:42.429Z
- Market snapshot: 2026-10-08T21:18:31.053Z
- Candidate universe: 24396; deep validation pool: 249; feasible: 179
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 2
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

- raw_contracts: `50181`
- eligible_contracts: `43457`
- market_executable_contracts: `24396`
- snapshot_candidates: `24396`
- candidate_pool: `607`
- location_executable: `249`
- feasible: `179`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `2`
- research_watch: `161`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18837`
- MARKET_INELIGIBLE_SINGLETON: `6079`
- UNSAFE_OR_UNVERIFIED_LOCATION: `358`
- HIGHSEC_RESTRICTED_CAPITAL: `67`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- LIST_DATA_INCOMPLETE: `4`
- SKIN_DOMINANT: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
