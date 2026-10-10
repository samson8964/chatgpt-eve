# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T11:05:55.896Z
- Market snapshot: 2026-10-10T11:19:11.538Z
- Candidate universe: 24643; deep validation pool: 278; feasible: 210
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 12
- RESEARCH: 155
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

- raw_contracts: `50369`
- eligible_contracts: `43698`
- market_executable_contracts: `24643`
- snapshot_candidates: `24643`
- candidate_pool: `610`
- location_executable: `278`
- feasible: `210`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `12`
- research_watch: `155`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18838`
- MARKET_INELIGIBLE_SINGLETON: `6248`
- UNSAFE_OR_UNVERIFIED_LOCATION: `332`
- HIGHSEC_RESTRICTED_CAPITAL: `63`
- FATAL_OR_ACCESS_UNVERIFIED: `17`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `4`
