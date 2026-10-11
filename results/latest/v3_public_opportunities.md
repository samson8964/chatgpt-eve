# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T22:01:36.855Z
- Market snapshot: 2026-10-11T22:18:35.870Z
- Candidate universe: 24916; deep validation pool: 263; feasible: 181
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
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

- raw_contracts: `50898`
- eligible_contracts: `44191`
- market_executable_contracts: `24916`
- snapshot_candidates: `24916`
- candidate_pool: `611`
- location_executable: `263`
- feasible: `181`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `160`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `19039`
- MARKET_INELIGIBLE_SINGLETON: `6462`
- UNSAFE_OR_UNVERIFIED_LOCATION: `348`
- HIGHSEC_RESTRICTED_CAPITAL: `77`
- BARTER_PROCUREMENT_INCOMPLETE: `9`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `3`
- FATAL_OR_ACCESS_UNVERIFIED: `2`
