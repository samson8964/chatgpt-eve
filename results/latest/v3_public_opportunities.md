# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T20:01:29.377Z
- Market snapshot: 2026-10-09T20:18:33.022Z
- Candidate universe: 24542; deep validation pool: 248; feasible: 178
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 161
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

- raw_contracts: `50242`
- eligible_contracts: `43589`
- market_executable_contracts: `24542`
- snapshot_candidates: `24542`
- candidate_pool: `610`
- location_executable: `248`
- feasible: `178`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `161`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18835`
- MARKET_INELIGIBLE_SINGLETON: `6182`
- UNSAFE_OR_UNVERIFIED_LOCATION: `362`
- HIGHSEC_RESTRICTED_CAPITAL: `66`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- LIST_DATA_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
- SKIN_DOMINANT: `4`
