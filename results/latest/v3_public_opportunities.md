# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T03:31:44.116Z
- Market snapshot: 2026-10-11T03:48:40.031Z
- Candidate universe: 24628; deep validation pool: 281; feasible: 205
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 157
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

- raw_contracts: `50204`
- eligible_contracts: `43695`
- market_executable_contracts: `24628`
- snapshot_candidates: `24628`
- candidate_pool: `610`
- location_executable: `281`
- feasible: `205`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `10`
- research_watch: `157`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18840`
- MARKET_INELIGIBLE_SINGLETON: `6211`
- UNSAFE_OR_UNVERIFIED_LOCATION: `329`
- HIGHSEC_RESTRICTED_CAPITAL: `71`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `3`
