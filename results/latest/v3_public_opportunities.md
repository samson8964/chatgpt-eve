# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T04:32:00.330Z
- Market snapshot: 2026-10-09T04:48:21.916Z
- Candidate universe: 24292; deep validation pool: 264; feasible: 208
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 153
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

- raw_contracts: `50096`
- eligible_contracts: `43366`
- market_executable_contracts: `24292`
- snapshot_candidates: `24292`
- candidate_pool: `607`
- location_executable: `264`
- feasible: `208`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `11`
- research_watch: `153`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18851`
- MARKET_INELIGIBLE_SINGLETON: `6044`
- UNSAFE_OR_UNVERIFIED_LOCATION: `343`
- HIGHSEC_RESTRICTED_CAPITAL: `52`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- SKIN_DOMINANT: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- LIST_TOO_SLOW: `3`
