# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T23:31:40.195Z
- Market snapshot: 2026-10-08T23:48:28.663Z
- Candidate universe: 24372; deep validation pool: 238; feasible: 181
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 160
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

- raw_contracts: `50089`
- eligible_contracts: `43440`
- market_executable_contracts: `24372`
- snapshot_candidates: `24372`
- candidate_pool: `607`
- location_executable: `238`
- feasible: `181`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `5`
- research_watch: `160`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18846`
- MARKET_INELIGIBLE_SINGLETON: `6047`
- UNSAFE_OR_UNVERIFIED_LOCATION: `369`
- HIGHSEC_RESTRICTED_CAPITAL: `54`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `5`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
- LIST_DATA_INCOMPLETE: `3`
