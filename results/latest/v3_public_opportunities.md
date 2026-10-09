# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T18:01:27.042Z
- Market snapshot: 2026-10-09T17:48:41.407Z
- Candidate universe: 24472; deep validation pool: 270; feasible: 194
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 161
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

- raw_contracts: `50273`
- eligible_contracts: `43554`
- market_executable_contracts: `24472`
- snapshot_candidates: `24472`
- candidate_pool: `610`
- location_executable: `270`
- feasible: `194`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `5`
- research_watch: `161`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18871`
- MARKET_INELIGIBLE_SINGLETON: `6203`
- UNSAFE_OR_UNVERIFIED_LOCATION: `340`
- HIGHSEC_RESTRICTED_CAPITAL: `72`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
- NO_EXECUTABLE_ITEMS: `1`
