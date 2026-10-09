# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T07:31:41.377Z
- Market snapshot: 2026-10-09T07:48:26.097Z
- Candidate universe: 24199; deep validation pool: 246; feasible: 229
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
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

- raw_contracts: `50084`
- eligible_contracts: `43280`
- market_executable_contracts: `24199`
- snapshot_candidates: `24199`
- candidate_pool: `607`
- location_executable: `246`
- feasible: `229`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `158`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18862`
- MARKET_INELIGIBLE_SINGLETON: `6044`
- UNSAFE_OR_UNVERIFIED_LOCATION: `361`
- HIGHSEC_RESTRICTED_CAPITAL: `13`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
- SKIN_DOMINANT: `4`
- LIST_DATA_INCOMPLETE: `3`
