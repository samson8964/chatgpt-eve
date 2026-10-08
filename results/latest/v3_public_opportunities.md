# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T20:31:46.050Z
- Market snapshot: 2026-10-08T20:18:31.310Z
- Candidate universe: 24410; deep validation pool: 245; feasible: 189
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 156
- FORMAL MAIL: 5

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50160`
- eligible_contracts: `43477`
- market_executable_contracts: `24410`
- snapshot_candidates: `24410`
- candidate_pool: `607`
- location_executable: `245`
- feasible: `189`
- full_cash: `5`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `8`
- research_watch: `156`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18844`
- MARKET_INELIGIBLE_SINGLETON: `6099`
- UNSAFE_OR_UNVERIFIED_LOCATION: `362`
- HIGHSEC_RESTRICTED_CAPITAL: `55`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- LIST_DATA_INCOMPLETE: `4`
- LIST_TOO_SLOW: `3`
- SKIN_DOMINANT: `1`
