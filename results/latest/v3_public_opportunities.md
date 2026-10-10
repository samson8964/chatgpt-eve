# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T05:01:39.789Z
- Market snapshot: 2026-10-10T05:18:23.332Z
- Candidate universe: 24750; deep validation pool: 245; feasible: 176
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 157
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

- raw_contracts: `50420`
- eligible_contracts: `43834`
- market_executable_contracts: `24750`
- snapshot_candidates: `24750`
- candidate_pool: `610`
- location_executable: `245`
- feasible: `176`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `10`
- research_watch: `157`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18866`
- MARKET_INELIGIBLE_SINGLETON: `6283`
- UNSAFE_OR_UNVERIFIED_LOCATION: `365`
- HIGHSEC_RESTRICTED_CAPITAL: `67`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- FATAL_OR_ACCESS_UNVERIFIED: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- SKIN_DOMINANT: `2`
