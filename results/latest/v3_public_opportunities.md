# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T23:31:36.226Z
- Market snapshot: 2026-10-07T23:18:22.387Z
- Candidate universe: 24562; deep validation pool: 222; feasible: 163
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 12
- RESEARCH: 139
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

- raw_contracts: `49964`
- eligible_contracts: `43381`
- market_executable_contracts: `24562`
- snapshot_candidates: `24562`
- candidate_pool: `605`
- location_executable: `222`
- feasible: `163`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `12`
- research_watch: `139`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18597`
- MARKET_INELIGIBLE_SINGLETON: `5997`
- UNSAFE_OR_UNVERIFIED_LOCATION: `383`
- HIGHSEC_RESTRICTED_CAPITAL: `56`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- SKIN_DOMINANT: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
