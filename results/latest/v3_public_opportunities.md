# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T22:31:39.571Z
- Market snapshot: 2026-10-08T22:18:28.029Z
- Candidate universe: 24384; deep validation pool: 249; feasible: 191
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 157
- FORMAL MAIL: 4

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50113`
- eligible_contracts: `43437`
- market_executable_contracts: `24384`
- snapshot_candidates: `24384`
- candidate_pool: `607`
- location_executable: `249`
- feasible: `191`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `157`
- mail_eligible: `4`

## Rejection reasons

- BPC_ROUTED: `18828`
- MARKET_INELIGIBLE_SINGLETON: `6067`
- UNSAFE_OR_UNVERIFIED_LOCATION: `358`
- HIGHSEC_RESTRICTED_CAPITAL: `56`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- LIST_DATA_INCOMPLETE: `4`
- LIST_TOO_SLOW: `3`
- SKIN_DOMINANT: `2`
