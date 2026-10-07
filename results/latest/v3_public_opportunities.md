# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T11:10:23.630Z
- Market snapshot: 2026-10-07T11:19:04.134Z
- Candidate universe: 6426; deep validation pool: 233; feasible: 189
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 3
- RESEARCH: 159
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

- raw_contracts: `10120`
- eligible_contracts: `8467`
- market_executable_contracts: `6426`
- snapshot_candidates: `6426`
- candidate_pool: `603`
- location_executable: `233`
- feasible: `189`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `3`
- research_watch: `159`
- mail_eligible: `0`

## Rejection reasons

- MARKET_INELIGIBLE_SINGLETON: `4741`
- BPC_ROUTED: `2004`
- UNSAFE_OR_UNVERIFIED_LOCATION: `370`
- HIGHSEC_RESTRICTED_CAPITAL: `43`
- FATAL_OR_ACCESS_UNVERIFIED: `19`
- LIST_DATA_INCOMPLETE: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
- LIST_TOO_SLOW: `2`
- SKIN_DOMINANT: `1`
