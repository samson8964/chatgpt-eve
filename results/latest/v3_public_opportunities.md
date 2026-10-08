# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T19:31:26.474Z
- Market snapshot: 2026-10-08T18:48:53.568Z
- Candidate universe: 24409; deep validation pool: 250; feasible: 185
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 157
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

- raw_contracts: `50168`
- eligible_contracts: `43456`
- market_executable_contracts: `24409`
- snapshot_candidates: `24409`
- candidate_pool: `607`
- location_executable: `250`
- feasible: `185`
- full_cash: `3`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `6`
- research_watch: `157`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18827`
- MARKET_INELIGIBLE_SINGLETON: `6105`
- UNSAFE_OR_UNVERIFIED_LOCATION: `357`
- HIGHSEC_RESTRICTED_CAPITAL: `61`
- FATAL_OR_ACCESS_UNVERIFIED: `12`
- SKIN_DOMINANT: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
- LIST_DATA_INCOMPLETE: `3`
