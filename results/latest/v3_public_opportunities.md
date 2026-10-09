# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T09:02:04.951Z
- Market snapshot: 2026-10-09T08:48:35.054Z
- Candidate universe: 24206; deep validation pool: 263; feasible: 207
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 162
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

- raw_contracts: `50076`
- eligible_contracts: `43334`
- market_executable_contracts: `24206`
- snapshot_candidates: `24206`
- candidate_pool: `610`
- location_executable: `263`
- feasible: `207`
- full_cash: `1`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `7`
- research_watch: `162`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18905`
- MARKET_INELIGIBLE_SINGLETON: `6045`
- UNSAFE_OR_UNVERIFIED_LOCATION: `347`
- HIGHSEC_RESTRICTED_CAPITAL: `52`
- FATAL_OR_ACCESS_UNVERIFIED: `20`
- BARTER_PROCUREMENT_INCOMPLETE: `9`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `2`
