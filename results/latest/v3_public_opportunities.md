# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T11:31:50.731Z
- Market snapshot: 2026-10-09T11:48:37.421Z
- Candidate universe: 24379; deep validation pool: 230; feasible: 166
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 146
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

- raw_contracts: `50243`
- eligible_contracts: `43513`
- market_executable_contracts: `24379`
- snapshot_candidates: `24379`
- candidate_pool: `610`
- location_executable: `230`
- feasible: `166`
- full_cash: `4`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `10`
- research_watch: `146`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18913`
- MARKET_INELIGIBLE_SINGLETON: `6230`
- UNSAFE_OR_UNVERIFIED_LOCATION: `380`
- HIGHSEC_RESTRICTED_CAPITAL: `62`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_DATA_INCOMPLETE: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `2`
