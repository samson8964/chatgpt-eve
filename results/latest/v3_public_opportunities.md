# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T08:01:38.125Z
- Market snapshot: 2026-10-09T08:18:33.104Z
- Candidate universe: 24217; deep validation pool: 248; feasible: 171
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 152
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

- raw_contracts: `50076`
- eligible_contracts: `43286`
- market_executable_contracts: `24217`
- snapshot_candidates: `24217`
- candidate_pool: `608`
- location_executable: `248`
- feasible: `171`
- full_cash: `2`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `8`
- research_watch: `152`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18854`
- MARKET_INELIGIBLE_SINGLETON: `6040`
- UNSAFE_OR_UNVERIFIED_LOCATION: `360`
- HIGHSEC_RESTRICTED_CAPITAL: `73`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- LIST_DATA_INCOMPLETE: `5`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- LIST_TOO_SLOW: `4`
- NO_EXECUTABLE_ITEMS: `2`
- SKIN_DOMINANT: `2`
