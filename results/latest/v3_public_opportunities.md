# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T05:01:39.789Z
- Market snapshot: 2026-10-10T04:48:27.087Z
- Candidate universe: 24749; deep validation pool: 244; feasible: 172
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 155
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

- raw_contracts: `50420`
- eligible_contracts: `43835`
- market_executable_contracts: `24749`
- snapshot_candidates: `24749`
- candidate_pool: `610`
- location_executable: `244`
- feasible: `172`
- full_cash: `2`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `8`
- research_watch: `155`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18867`
- MARKET_INELIGIBLE_SINGLETON: `6285`
- UNSAFE_OR_UNVERIFIED_LOCATION: `366`
- HIGHSEC_RESTRICTED_CAPITAL: `67`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- LIST_DATA_INCOMPLETE: `6`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `4`
