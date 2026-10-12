# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T09:02:02.817Z
- Market snapshot: 2026-10-12T08:48:45.229Z
- Candidate universe: 25069; deep validation pool: 240; feasible: 175
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 163
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

- raw_contracts: `50846`
- eligible_contracts: `44343`
- market_executable_contracts: `25069`
- snapshot_candidates: `25069`
- candidate_pool: `611`
- location_executable: `240`
- feasible: `175`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `5`
- research_watch: `163`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19046`
- MARKET_INELIGIBLE_SINGLETON: `6485`
- UNSAFE_OR_UNVERIFIED_LOCATION: `371`
- HIGHSEC_RESTRICTED_CAPITAL: `60`
- BARTER_PROCUREMENT_INCOMPLETE: `10`
- LIST_DATA_INCOMPLETE: `7`
- SKIN_DOMINANT: `5`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `5`
