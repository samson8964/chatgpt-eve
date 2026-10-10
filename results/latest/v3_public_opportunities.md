# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T06:31:51.630Z
- Market snapshot: 2026-10-10T06:48:55.401Z
- Candidate universe: 24757; deep validation pool: 265; feasible: 188
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
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

- raw_contracts: `50441`
- eligible_contracts: `43825`
- market_executable_contracts: `24757`
- snapshot_candidates: `24757`
- candidate_pool: `610`
- location_executable: `265`
- feasible: `188`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `159`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18851`
- MARKET_INELIGIBLE_SINGLETON: `6294`
- UNSAFE_OR_UNVERIFIED_LOCATION: `345`
- HIGHSEC_RESTRICTED_CAPITAL: `72`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- SKIN_DOMINANT: `5`
- FATAL_OR_ACCESS_UNVERIFIED: `4`
- LIST_TOO_SLOW: `2`
