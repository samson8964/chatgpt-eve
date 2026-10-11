# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T05:01:38.110Z
- Market snapshot: 2026-10-11T05:18:37.678Z
- Candidate universe: 24630; deep validation pool: 260; feasible: 188
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 11
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

- raw_contracts: `50176`
- eligible_contracts: `43707`
- market_executable_contracts: `24630`
- snapshot_candidates: `24630`
- candidate_pool: `610`
- location_executable: `260`
- feasible: `188`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `11`
- research_watch: `157`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18849`
- MARKET_INELIGIBLE_SINGLETON: `6233`
- UNSAFE_OR_UNVERIFIED_LOCATION: `350`
- HIGHSEC_RESTRICTED_CAPITAL: `67`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `1`
