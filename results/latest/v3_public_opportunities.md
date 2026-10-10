# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T09:02:02.909Z
- Market snapshot: 2026-10-10T08:48:32.257Z
- Candidate universe: 24684; deep validation pool: 264; feasible: 192
- FULL_CASH: 6
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 156
- FORMAL MAIL: 6

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50370`
- eligible_contracts: `43718`
- market_executable_contracts: `24684`
- snapshot_candidates: `24684`
- candidate_pool: `610`
- location_executable: `264`
- feasible: `192`
- full_cash: `6`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `11`
- research_watch: `156`
- mail_eligible: `6`

## Rejection reasons

- BPC_ROUTED: `18816`
- MARKET_INELIGIBLE_SINGLETON: `6271`
- UNSAFE_OR_UNVERIFIED_LOCATION: `346`
- HIGHSEC_RESTRICTED_CAPITAL: `69`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
- LIST_DATA_INCOMPLETE: `1`
