# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T20:31:41.687Z
- Market snapshot: 2026-10-09T20:48:37.302Z
- Candidate universe: 24600; deep validation pool: 316; feasible: 244
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
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

- raw_contracts: `50305`
- eligible_contracts: `43661`
- market_executable_contracts: `24600`
- snapshot_candidates: `24600`
- candidate_pool: `611`
- location_executable: `316`
- feasible: `244`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `160`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18848`
- MARKET_INELIGIBLE_SINGLETON: `6227`
- UNSAFE_OR_UNVERIFIED_LOCATION: `295`
- HIGHSEC_RESTRICTED_CAPITAL: `69`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
- FATAL_OR_ACCESS_UNVERIFIED: `3`
