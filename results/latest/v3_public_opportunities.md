# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T04:32:00.330Z
- Market snapshot: 2026-10-09T04:18:23.633Z
- Candidate universe: 24299; deep validation pool: 263; feasible: 210
- FULL_CASH: 7
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 157
- FORMAL MAIL: 5

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50096`
- eligible_contracts: `43373`
- market_executable_contracts: `24299`
- snapshot_candidates: `24299`
- candidate_pool: `607`
- location_executable: `263`
- feasible: `210`
- full_cash: `7`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `157`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18853`
- MARKET_INELIGIBLE_SINGLETON: `6043`
- UNSAFE_OR_UNVERIFIED_LOCATION: `344`
- HIGHSEC_RESTRICTED_CAPITAL: `51`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- BARTER_PROCUREMENT_INCOMPLETE: `5`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `2`
