# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T04:31:37.478Z
- Market snapshot: 2026-10-12T04:18:28.758Z
- Candidate universe: 25028; deep validation pool: 282; feasible: 209
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 159
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

- raw_contracts: `50894`
- eligible_contracts: `44328`
- market_executable_contracts: `25028`
- snapshot_candidates: `25028`
- candidate_pool: `611`
- location_executable: `282`
- feasible: `209`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `159`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `19067`
- MARKET_INELIGIBLE_SINGLETON: `6524`
- UNSAFE_OR_UNVERIFIED_LOCATION: `329`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `3`
