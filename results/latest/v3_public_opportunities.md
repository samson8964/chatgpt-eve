# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T06:02:18.204Z
- Market snapshot: 2026-10-09T06:18:24.186Z
- Candidate universe: 24252; deep validation pool: 237; feasible: 185
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 12
- RESEARCH: 152
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

- raw_contracts: `50092`
- eligible_contracts: `43286`
- market_executable_contracts: `24252`
- snapshot_candidates: `24252`
- candidate_pool: `607`
- location_executable: `237`
- feasible: `185`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `12`
- research_watch: `152`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18811`
- MARKET_INELIGIBLE_SINGLETON: `6049`
- UNSAFE_OR_UNVERIFIED_LOCATION: `370`
- HIGHSEC_RESTRICTED_CAPITAL: `51`
- FATAL_OR_ACCESS_UNVERIFIED: `13`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- SKIN_DOMINANT: `1`
