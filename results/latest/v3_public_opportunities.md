# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T04:01:37.668Z
- Market snapshot: 2026-10-12T03:48:39.164Z
- Candidate universe: 25029; deep validation pool: 283; feasible: 207
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 160
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

- raw_contracts: `50896`
- eligible_contracts: `44335`
- market_executable_contracts: `25029`
- snapshot_candidates: `25029`
- candidate_pool: `611`
- location_executable: `283`
- feasible: `207`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `160`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19070`
- MARKET_INELIGIBLE_SINGLETON: `6531`
- UNSAFE_OR_UNVERIFIED_LOCATION: `328`
- HIGHSEC_RESTRICTED_CAPITAL: `73`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
