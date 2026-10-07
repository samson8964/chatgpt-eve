# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T20:01:20.435Z
- Market snapshot: 2026-10-07T19:48:25.525Z
- Candidate universe: 24559; deep validation pool: 217; feasible: 149
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 140
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

- raw_contracts: `49922`
- eligible_contracts: `43403`
- market_executable_contracts: `24559`
- snapshot_candidates: `24559`
- candidate_pool: `605`
- location_executable: `217`
- feasible: `149`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `140`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18621`
- MARKET_INELIGIBLE_SINGLETON: `5986`
- UNSAFE_OR_UNVERIFIED_LOCATION: `388`
- HIGHSEC_RESTRICTED_CAPITAL: `64`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- FATAL_OR_ACCESS_UNVERIFIED: `3`
