# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T18:01:36.039Z
- Market snapshot: 2026-10-12T18:18:43.661Z
- Candidate universe: 25114; deep validation pool: 229; feasible: 156
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 135
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

- raw_contracts: `50797`
- eligible_contracts: `44334`
- market_executable_contracts: `25114`
- snapshot_candidates: `25114`
- candidate_pool: `611`
- location_executable: `229`
- feasible: `156`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `135`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18991`
- MARKET_INELIGIBLE_SINGLETON: `6542`
- UNSAFE_OR_UNVERIFIED_LOCATION: `382`
- HIGHSEC_RESTRICTED_CAPITAL: `66`
- FATAL_OR_ACCESS_UNVERIFIED: `16`
- SKIN_DOMINANT: `7`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
- LIST_DATA_INCOMPLETE: `5`
