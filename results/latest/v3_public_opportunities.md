# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T18:01:21.882Z
- Market snapshot: 2026-10-07T17:48:28.152Z
- Candidate universe: 24478; deep validation pool: 214; feasible: 152
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 137
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

- raw_contracts: `49656`
- eligible_contracts: `43159`
- market_executable_contracts: `24478`
- snapshot_candidates: `24478`
- candidate_pool: `605`
- location_executable: `214`
- feasible: `152`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `137`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18462`
- MARKET_INELIGIBLE_SINGLETON: `5996`
- UNSAFE_OR_UNVERIFIED_LOCATION: `391`
- HIGHSEC_RESTRICTED_CAPITAL: `59`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
- LIST_DATA_INCOMPLETE: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
