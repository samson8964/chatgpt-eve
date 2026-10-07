# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T18:01:21.882Z
- Market snapshot: 2026-10-07T17:48:28.152Z
- Candidate universe: 24475; deep validation pool: 212; feasible: 160
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 138
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

- raw_contracts: `49656`
- eligible_contracts: `43152`
- market_executable_contracts: `24475`
- snapshot_candidates: `24475`
- candidate_pool: `605`
- location_executable: `212`
- feasible: `160`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `11`
- research_watch: `138`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18461`
- MARKET_INELIGIBLE_SINGLETON: `5997`
- UNSAFE_OR_UNVERIFIED_LOCATION: `393`
- HIGHSEC_RESTRICTED_CAPITAL: `48`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- BARTER_PROCUREMENT_INCOMPLETE: `5`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `3`
