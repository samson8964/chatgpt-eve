# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T18:01:45.762Z
- Market snapshot: 2026-10-11T18:48:51.265Z
- Candidate universe: 24717; deep validation pool: 250; feasible: 174
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 158
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

- raw_contracts: `50663`
- eligible_contracts: `43964`
- market_executable_contracts: `24717`
- snapshot_candidates: `24717`
- candidate_pool: `611`
- location_executable: `250`
- feasible: `174`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `5`
- research_watch: `158`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `19011`
- MARKET_INELIGIBLE_SINGLETON: `6374`
- UNSAFE_OR_UNVERIFIED_LOCATION: `361`
- HIGHSEC_RESTRICTED_CAPITAL: `70`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `6`
- LIST_DATA_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
