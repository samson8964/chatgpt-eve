# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T11:40:39.924Z
- Market snapshot: 2026-10-07T11:48:25.959Z
- Candidate universe: 24444; deep validation pool: 222; feasible: 156
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 3
- RESEARCH: 138
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

- raw_contracts: `49752`
- eligible_contracts: `43190`
- market_executable_contracts: `24444`
- snapshot_candidates: `24444`
- candidate_pool: `605`
- location_executable: `222`
- feasible: `156`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `3`
- research_watch: `138`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18406`
- MARKET_INELIGIBLE_SINGLETON: `5983`
- UNSAFE_OR_UNVERIFIED_LOCATION: `383`
- HIGHSEC_RESTRICTED_CAPITAL: `62`
- FATAL_OR_ACCESS_UNVERIFIED: `14`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
- LIST_DATA_INCOMPLETE: `2`
