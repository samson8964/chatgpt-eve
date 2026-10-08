# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T05:01:38.959Z
- Market snapshot: 2026-10-08T04:48:24.084Z
- Candidate universe: 24554; deep validation pool: 259; feasible: 250
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 160
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

- raw_contracts: `49845`
- eligible_contracts: `43314`
- market_executable_contracts: `24554`
- snapshot_candidates: `24554`
- candidate_pool: `605`
- location_executable: `259`
- feasible: `250`
- full_cash: `5`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `4`
- research_watch: `160`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18541`
- MARKET_INELIGIBLE_SINGLETON: `5991`
- UNSAFE_OR_UNVERIFIED_LOCATION: `346`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- HIGHSEC_RESTRICTED_CAPITAL: `5`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- LIST_TOO_SLOW: `3`
- NO_EXECUTABLE_ITEMS: `2`
- SKIN_DOMINANT: `2`
