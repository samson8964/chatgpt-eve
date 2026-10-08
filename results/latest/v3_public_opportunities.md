# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T01:31:36.380Z
- Market snapshot: 2026-10-08T01:48:22.937Z
- Candidate universe: 24562; deep validation pool: 243; feasible: 181
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
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

- raw_contracts: `49957`
- eligible_contracts: `43416`
- market_executable_contracts: `24562`
- snapshot_candidates: `24562`
- candidate_pool: `605`
- location_executable: `243`
- feasible: `181`
- full_cash: `5`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `155`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18635`
- MARKET_INELIGIBLE_SINGLETON: `5995`
- UNSAFE_OR_UNVERIFIED_LOCATION: `362`
- HIGHSEC_RESTRICTED_CAPITAL: `58`
- FATAL_OR_ACCESS_UNVERIFIED: `13`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_DATA_INCOMPLETE: `3`
