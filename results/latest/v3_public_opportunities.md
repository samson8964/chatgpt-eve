# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T04:01:35.457Z
- Market snapshot: 2026-10-08T03:48:30.363Z
- Candidate universe: 24540; deep validation pool: 258; feasible: 248
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 160
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

- raw_contracts: `49894`
- eligible_contracts: `43367`
- market_executable_contracts: `24540`
- snapshot_candidates: `24540`
- candidate_pool: `605`
- location_executable: `258`
- feasible: `248`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `160`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18604`
- MARKET_INELIGIBLE_SINGLETON: `5992`
- UNSAFE_OR_UNVERIFIED_LOCATION: `347`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- HIGHSEC_RESTRICTED_CAPITAL: `7`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
