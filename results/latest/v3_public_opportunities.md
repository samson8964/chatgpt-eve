# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T11:05:12.059Z
- Market snapshot: 2026-10-11T11:19:22.589Z
- Candidate universe: 24570; deep validation pool: 251; feasible: 175
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 158
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

- raw_contracts: `50308`
- eligible_contracts: `43793`
- market_executable_contracts: `24570`
- snapshot_candidates: `24570`
- candidate_pool: `610`
- location_executable: `251`
- feasible: `175`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `158`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18994`
- MARKET_INELIGIBLE_SINGLETON: `6233`
- UNSAFE_OR_UNVERIFIED_LOCATION: `359`
- HIGHSEC_RESTRICTED_CAPITAL: `70`
- SKIN_DOMINANT: `6`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_TOO_SLOW: `6`
- LIST_DATA_INCOMPLETE: `5`
- FATAL_OR_ACCESS_UNVERIFIED: `3`
