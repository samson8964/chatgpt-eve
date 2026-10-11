# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T15:31:44.083Z
- Market snapshot: 2026-10-11T15:48:40.551Z
- Candidate universe: 24541; deep validation pool: 265; feasible: 190
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 160
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

- raw_contracts: `50397`
- eligible_contracts: `43821`
- market_executable_contracts: `24541`
- snapshot_candidates: `24541`
- candidate_pool: `610`
- location_executable: `265`
- feasible: `190`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `160`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19056`
- MARKET_INELIGIBLE_SINGLETON: `6251`
- UNSAFE_OR_UNVERIFIED_LOCATION: `345`
- HIGHSEC_RESTRICTED_CAPITAL: `69`
- SKIN_DOMINANT: `6`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_TOO_SLOW: `4`
- FATAL_OR_ACCESS_UNVERIFIED: `2`
