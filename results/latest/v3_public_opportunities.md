# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T13:31:25.990Z
- Market snapshot: 2026-10-08T13:18:34.851Z
- Candidate universe: 24543; deep validation pool: 236; feasible: 167
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 149
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

- raw_contracts: `50001`
- eligible_contracts: `43396`
- market_executable_contracts: `24543`
- snapshot_candidates: `24543`
- candidate_pool: `606`
- location_executable: `236`
- feasible: `167`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `149`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18627`
- MARKET_INELIGIBLE_SINGLETON: `6066`
- UNSAFE_OR_UNVERIFIED_LOCATION: `370`
- HIGHSEC_RESTRICTED_CAPITAL: `65`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- LIST_DATA_INCOMPLETE: `5`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
