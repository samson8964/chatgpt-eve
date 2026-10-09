# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T20:01:29.377Z
- Market snapshot: 2026-10-09T19:48:32.450Z
- Candidate universe: 24548; deep validation pool: 256; feasible: 243
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 162
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

- raw_contracts: `50242`
- eligible_contracts: `43596`
- market_executable_contracts: `24548`
- snapshot_candidates: `24548`
- candidate_pool: `610`
- location_executable: `256`
- feasible: `243`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `162`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18835`
- MARKET_INELIGIBLE_SINGLETON: `6188`
- UNSAFE_OR_UNVERIFIED_LOCATION: `354`
- HIGHSEC_RESTRICTED_CAPITAL: `10`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- LIST_TOO_SLOW: `6`
- SKIN_DOMINANT: `3`
- LIST_DATA_INCOMPLETE: `1`
