# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T17:32:07.391Z
- Market snapshot: 2026-10-11T17:48:44.075Z
- Candidate universe: 24709; deep validation pool: 261; feasible: 186
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 159
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

- raw_contracts: `50628`
- eligible_contracts: `43968`
- market_executable_contracts: `24709`
- snapshot_candidates: `24709`
- candidate_pool: `610`
- location_executable: `261`
- feasible: `186`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `159`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19031`
- MARKET_INELIGIBLE_SINGLETON: `6380`
- UNSAFE_OR_UNVERIFIED_LOCATION: `349`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- SKIN_DOMINANT: `7`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `4`
- LIST_TOO_SLOW: `4`
