# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T00:01:40.878Z
- Market snapshot: 2026-10-11T00:18:37.860Z
- Candidate universe: 24600; deep validation pool: 279; feasible: 202
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 159
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

- raw_contracts: `50277`
- eligible_contracts: `43728`
- market_executable_contracts: `24600`
- snapshot_candidates: `24600`
- candidate_pool: `610`
- location_executable: `279`
- feasible: `202`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `159`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18905`
- MARKET_INELIGIBLE_SINGLETON: `6234`
- UNSAFE_OR_UNVERIFIED_LOCATION: `331`
- HIGHSEC_RESTRICTED_CAPITAL: `73`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
