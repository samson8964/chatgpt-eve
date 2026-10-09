# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T19:01:49.860Z
- Market snapshot: 2026-10-09T18:48:52.766Z
- Candidate universe: 24483; deep validation pool: 257; feasible: 192
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 163
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

- raw_contracts: `50218`
- eligible_contracts: `43576`
- market_executable_contracts: `24483`
- snapshot_candidates: `24483`
- candidate_pool: `610`
- location_executable: `257`
- feasible: `192`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `163`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18880`
- MARKET_INELIGIBLE_SINGLETON: `6190`
- UNSAFE_OR_UNVERIFIED_LOCATION: `353`
- HIGHSEC_RESTRICTED_CAPITAL: `61`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_TOO_SLOW: `5`
- SKIN_DOMINANT: `4`
- LIST_DATA_INCOMPLETE: `1`
