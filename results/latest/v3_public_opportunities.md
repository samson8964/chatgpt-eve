# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T00:01:46.161Z
- Market snapshot: 2026-10-07T23:48:25.413Z
- Candidate universe: 24556; deep validation pool: 232; feasible: 216
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 157
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

- raw_contracts: `49959`
- eligible_contracts: `43400`
- market_executable_contracts: `24556`
- snapshot_candidates: `24556`
- candidate_pool: `605`
- location_executable: `232`
- feasible: `216`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `5`
- research_watch: `157`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18621`
- MARKET_INELIGIBLE_SINGLETON: `5999`
- UNSAFE_OR_UNVERIFIED_LOCATION: `373`
- HIGHSEC_RESTRICTED_CAPITAL: `13`
- FATAL_OR_ACCESS_UNVERIFIED: `11`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
- LIST_DATA_INCOMPLETE: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
