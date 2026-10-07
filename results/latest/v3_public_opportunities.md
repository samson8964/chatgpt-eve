# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T22:31:50.701Z
- Market snapshot: 2026-10-07T22:18:27.127Z
- Candidate universe: 24543; deep validation pool: 226; feasible: 163
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 140
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

- raw_contracts: `49946`
- eligible_contracts: `43417`
- market_executable_contracts: `24543`
- snapshot_candidates: `24543`
- candidate_pool: `605`
- location_executable: `226`
- feasible: `163`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `140`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18649`
- MARKET_INELIGIBLE_SINGLETON: `5993`
- UNSAFE_OR_UNVERIFIED_LOCATION: `379`
- HIGHSEC_RESTRICTED_CAPITAL: `59`
- FATAL_OR_ACCESS_UNVERIFIED: `11`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
