# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T06:01:35.595Z
- Market snapshot: 2026-10-08T06:18:27.809Z
- Candidate universe: 24570; deep validation pool: 247; feasible: 194
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 156
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

- raw_contracts: `49836`
- eligible_contracts: `43297`
- market_executable_contracts: `24570`
- snapshot_candidates: `24570`
- candidate_pool: `605`
- location_executable: `247`
- feasible: `194`
- full_cash: `4`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `8`
- research_watch: `156`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18508`
- MARKET_INELIGIBLE_SINGLETON: `5995`
- UNSAFE_OR_UNVERIFIED_LOCATION: `358`
- HIGHSEC_RESTRICTED_CAPITAL: `49`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- SKIN_DOMINANT: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- LIST_TOO_SLOW: `2`
- LIST_DATA_INCOMPLETE: `2`
