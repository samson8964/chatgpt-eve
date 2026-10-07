# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T19:31:25.009Z
- Market snapshot: 2026-10-07T19:48:25.525Z
- Candidate universe: 24573; deep validation pool: 210; feasible: 155
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 142
- FORMAL MAIL: 2

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `49919`
- eligible_contracts: `43412`
- market_executable_contracts: `24573`
- snapshot_candidates: `24573`
- candidate_pool: `605`
- location_executable: `210`
- feasible: `155`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `142`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18619`
- MARKET_INELIGIBLE_SINGLETON: `5996`
- UNSAFE_OR_UNVERIFIED_LOCATION: `395`
- HIGHSEC_RESTRICTED_CAPITAL: `53`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- FATAL_OR_ACCESS_UNVERIFIED: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- SKIN_DOMINANT: `2`
