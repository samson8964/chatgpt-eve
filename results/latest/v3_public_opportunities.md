# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T13:01:48.767Z
- Market snapshot: 2026-10-09T13:18:36.041Z
- Candidate universe: 24397; deep validation pool: 243; feasible: 184
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 160
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

- raw_contracts: `50288`
- eligible_contracts: `43588`
- market_executable_contracts: `24397`
- snapshot_candidates: `24397`
- candidate_pool: `610`
- location_executable: `243`
- feasible: `184`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `160`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18976`
- MARKET_INELIGIBLE_SINGLETON: `6229`
- UNSAFE_OR_UNVERIFIED_LOCATION: `367`
- HIGHSEC_RESTRICTED_CAPITAL: `59`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- LIST_TOO_SLOW: `5`
- LIST_DATA_INCOMPLETE: `5`
