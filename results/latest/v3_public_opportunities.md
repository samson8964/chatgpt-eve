# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T15:01:25.719Z
- Market snapshot: 2026-10-08T15:18:32.841Z
- Candidate universe: 24576; deep validation pool: 245; feasible: 175
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 4
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

- raw_contracts: `50073`
- eligible_contracts: `43547`
- market_executable_contracts: `24576`
- snapshot_candidates: `24576`
- candidate_pool: `606`
- location_executable: `245`
- feasible: `175`
- full_cash: `2`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `4`
- research_watch: `159`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18742`
- MARKET_INELIGIBLE_SINGLETON: `6100`
- UNSAFE_OR_UNVERIFIED_LOCATION: `361`
- HIGHSEC_RESTRICTED_CAPITAL: `66`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- SKIN_DOMINANT: `4`
- LIST_DATA_INCOMPLETE: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
