# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T05:01:38.596Z
- Market snapshot: 2026-10-09T04:48:21.916Z
- Candidate universe: 24292; deep validation pool: 245; feasible: 175
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 155
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

- raw_contracts: `50081`
- eligible_contracts: `43341`
- market_executable_contracts: `24292`
- snapshot_candidates: `24292`
- candidate_pool: `607`
- location_executable: `245`
- feasible: `175`
- full_cash: `3`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `6`
- research_watch: `155`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18827`
- MARKET_INELIGIBLE_SINGLETON: `6040`
- UNSAFE_OR_UNVERIFIED_LOCATION: `362`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- LIST_DATA_INCOMPLETE: `5`
- LIST_TOO_SLOW: `3`
- SKIN_DOMINANT: `2`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
