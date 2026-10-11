# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T19:31:52.360Z
- Market snapshot: 2026-10-11T19:48:48.423Z
- Candidate universe: 24877; deep validation pool: 245; feasible: 168
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 155
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

- raw_contracts: `50743`
- eligible_contracts: `44076`
- market_executable_contracts: `24877`
- snapshot_candidates: `24877`
- candidate_pool: `611`
- location_executable: `245`
- feasible: `168`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `155`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18963`
- MARKET_INELIGIBLE_SINGLETON: `6438`
- UNSAFE_OR_UNVERIFIED_LOCATION: `366`
- HIGHSEC_RESTRICTED_CAPITAL: `71`
- LIST_DATA_INCOMPLETE: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `6`
- LIST_TOO_SLOW: `5`
- FATAL_OR_ACCESS_UNVERIFIED: `3`
