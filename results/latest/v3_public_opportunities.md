# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T23:32:07.139Z
- Market snapshot: 2026-10-12T23:18:41.645Z
- Candidate universe: 25091; deep validation pool: 260; feasible: 143
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 131
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

- raw_contracts: `50728`
- eligible_contracts: `44466`
- market_executable_contracts: `25091`
- snapshot_candidates: `25091`
- candidate_pool: `612`
- location_executable: `260`
- feasible: `143`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `131`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19143`
- MARKET_INELIGIBLE_SINGLETON: `6476`
- UNSAFE_OR_UNVERIFIED_LOCATION: `352`
- HIGHSEC_RESTRICTED_CAPITAL: `111`
- LIST_DATA_INCOMPLETE: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `6`
- LIST_TOO_SLOW: `5`
- FATAL_OR_ACCESS_UNVERIFIED: `4`
