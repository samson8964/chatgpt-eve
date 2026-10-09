# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T00:31:36.605Z
- Market snapshot: 2026-10-09T00:18:23.722Z
- Candidate universe: 24304; deep validation pool: 245; feasible: 186
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 154
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

- raw_contracts: `50103`
- eligible_contracts: `43408`
- market_executable_contracts: `24304`
- snapshot_candidates: `24304`
- candidate_pool: `607`
- location_executable: `245`
- feasible: `186`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `10`
- research_watch: `154`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18881`
- MARKET_INELIGIBLE_SINGLETON: `6020`
- UNSAFE_OR_UNVERIFIED_LOCATION: `362`
- HIGHSEC_RESTRICTED_CAPITAL: `56`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
- LIST_DATA_INCOMPLETE: `3`
