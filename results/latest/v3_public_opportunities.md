# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T11:31:30.528Z
- Market snapshot: 2026-10-08T11:19:06.417Z
- Candidate universe: 24592; deep validation pool: 241; feasible: 188
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 155
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

- raw_contracts: `49923`
- eligible_contracts: `43389`
- market_executable_contracts: `24592`
- snapshot_candidates: `24592`
- candidate_pool: `605`
- location_executable: `241`
- feasible: `188`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `155`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18571`
- MARKET_INELIGIBLE_SINGLETON: `6020`
- UNSAFE_OR_UNVERIFIED_LOCATION: `364`
- HIGHSEC_RESTRICTED_CAPITAL: `50`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `2`
- LIST_DATA_INCOMPLETE: `2`
