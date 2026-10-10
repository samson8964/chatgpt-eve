# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T22:31:58.976Z
- Market snapshot: 2026-10-10T22:48:40.385Z
- Candidate universe: 24671; deep validation pool: 293; feasible: 217
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

- raw_contracts: `50381`
- eligible_contracts: `43797`
- market_executable_contracts: `24671`
- snapshot_candidates: `24671`
- candidate_pool: `610`
- location_executable: `293`
- feasible: `217`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `10`
- research_watch: `157`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18902`
- MARKET_INELIGIBLE_SINGLETON: `6300`
- UNSAFE_OR_UNVERIFIED_LOCATION: `317`
- HIGHSEC_RESTRICTED_CAPITAL: `72`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
