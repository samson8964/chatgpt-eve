# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T09:31:22.936Z
- Market snapshot: 2026-10-09T09:48:30.313Z
- Candidate universe: 24188; deep validation pool: 263; feasible: 207
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 165
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

- raw_contracts: `50079`
- eligible_contracts: `43305`
- market_executable_contracts: `24188`
- snapshot_candidates: `24188`
- candidate_pool: `610`
- location_executable: `263`
- feasible: `207`
- full_cash: `1`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `4`
- research_watch: `165`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18896`
- MARKET_INELIGIBLE_SINGLETON: `6045`
- UNSAFE_OR_UNVERIFIED_LOCATION: `347`
- HIGHSEC_RESTRICTED_CAPITAL: `52`
- FATAL_OR_ACCESS_UNVERIFIED: `18`
- BARTER_PROCUREMENT_INCOMPLETE: `9`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
