# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T22:31:40.054Z
- Market snapshot: 2026-10-12T22:48:34.361Z
- Candidate universe: 25086; deep validation pool: 255; feasible: 143
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 2
- RESEARCH: 130
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

- raw_contracts: `50726`
- eligible_contracts: `44441`
- market_executable_contracts: `25086`
- snapshot_candidates: `25086`
- candidate_pool: `612`
- location_executable: `255`
- feasible: `143`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `2`
- research_watch: `130`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19123`
- MARKET_INELIGIBLE_SINGLETON: `6471`
- UNSAFE_OR_UNVERIFIED_LOCATION: `357`
- HIGHSEC_RESTRICTED_CAPITAL: `108`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_DATA_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
- SKIN_DOMINANT: `4`
