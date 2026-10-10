# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T02:01:27.910Z
- Market snapshot: 2026-10-10T01:48:30.485Z
- Candidate universe: 24701; deep validation pool: 295; feasible: 233
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 160
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

- raw_contracts: `50447`
- eligible_contracts: `43777`
- market_executable_contracts: `24701`
- snapshot_candidates: `24701`
- candidate_pool: `610`
- location_executable: `295`
- feasible: `233`
- full_cash: `2`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `10`
- research_watch: `160`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18863`
- MARKET_INELIGIBLE_SINGLETON: `6282`
- UNSAFE_OR_UNVERIFIED_LOCATION: `315`
- HIGHSEC_RESTRICTED_CAPITAL: `59`
- BARTER_PROCUREMENT_INCOMPLETE: `10`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
