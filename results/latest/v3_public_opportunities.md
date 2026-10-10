# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T03:01:33.880Z
- Market snapshot: 2026-10-10T03:18:21.907Z
- Candidate universe: 24681; deep validation pool: 267; feasible: 192
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 157
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

- raw_contracts: `50436`
- eligible_contracts: `43765`
- market_executable_contracts: `24681`
- snapshot_candidates: `24681`
- candidate_pool: `610`
- location_executable: `267`
- feasible: `192`
- full_cash: `2`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `9`
- research_watch: `157`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18872`
- MARKET_INELIGIBLE_SINGLETON: `6285`
- UNSAFE_OR_UNVERIFIED_LOCATION: `343`
- HIGHSEC_RESTRICTED_CAPITAL: `71`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
