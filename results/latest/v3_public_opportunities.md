# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T15:01:27.234Z
- Market snapshot: 2026-10-12T15:18:36.438Z
- Candidate universe: 25004; deep validation pool: 250; feasible: 166
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 152
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

- raw_contracts: `50763`
- eligible_contracts: `44330`
- market_executable_contracts: `25004`
- snapshot_candidates: `25004`
- candidate_pool: `611`
- location_executable: `250`
- feasible: `166`
- full_cash: `1`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `4`
- research_watch: `152`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `19099`
- MARKET_INELIGIBLE_SINGLETON: `6547`
- UNSAFE_OR_UNVERIFIED_LOCATION: `361`
- HIGHSEC_RESTRICTED_CAPITAL: `77`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- SKIN_DOMINANT: `7`
- LIST_DATA_INCOMPLETE: `7`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
