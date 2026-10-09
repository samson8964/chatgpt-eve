# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T11:07:05.091Z
- Market snapshot: 2026-10-09T11:19:33.177Z
- Candidate universe: 24411; deep validation pool: 234; feasible: 178
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

- raw_contracts: `50256`
- eligible_contracts: `43575`
- market_executable_contracts: `24411`
- snapshot_candidates: `24411`
- candidate_pool: `610`
- location_executable: `234`
- feasible: `178`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `10`
- research_watch: `157`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18943`
- MARKET_INELIGIBLE_SINGLETON: `6241`
- UNSAFE_OR_UNVERIFIED_LOCATION: `376`
- HIGHSEC_RESTRICTED_CAPITAL: `53`
- BARTER_PROCUREMENT_INCOMPLETE: `9`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- LIST_DATA_INCOMPLETE: `6`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
