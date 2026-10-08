# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T22:31:39.571Z
- Market snapshot: 2026-10-08T22:48:28.931Z
- Candidate universe: 24389; deep validation pool: 250; feasible: 179
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 153
- FORMAL MAIL: 5

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50113`
- eligible_contracts: `43433`
- market_executable_contracts: `24389`
- snapshot_candidates: `24389`
- candidate_pool: `607`
- location_executable: `250`
- feasible: `179`
- full_cash: `5`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `153`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18827`
- MARKET_INELIGIBLE_SINGLETON: `6062`
- UNSAFE_OR_UNVERIFIED_LOCATION: `357`
- HIGHSEC_RESTRICTED_CAPITAL: `67`
- FATAL_OR_ACCESS_UNVERIFIED: `12`
- LIST_DATA_INCOMPLETE: `6`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
