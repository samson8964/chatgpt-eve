# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T15:31:44.083Z
- Market snapshot: 2026-10-11T16:18:40.690Z
- Candidate universe: 24505; deep validation pool: 265; feasible: 195
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 161
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

- raw_contracts: `50397`
- eligible_contracts: `43771`
- market_executable_contracts: `24505`
- snapshot_candidates: `24505`
- candidate_pool: `610`
- location_executable: `265`
- feasible: `195`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `161`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `19039`
- MARKET_INELIGIBLE_SINGLETON: `6250`
- UNSAFE_OR_UNVERIFIED_LOCATION: `345`
- HIGHSEC_RESTRICTED_CAPITAL: `65`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `5`
