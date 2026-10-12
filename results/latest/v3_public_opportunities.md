# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T09:31:40.402Z
- Market snapshot: 2026-10-12T09:18:31.921Z
- Candidate universe: 25049; deep validation pool: 247; feasible: 177
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 160
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

- raw_contracts: `50819`
- eligible_contracts: `44332`
- market_executable_contracts: `25049`
- snapshot_candidates: `25049`
- candidate_pool: `611`
- location_executable: `247`
- feasible: `177`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `160`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19053`
- MARKET_INELIGIBLE_SINGLETON: `6482`
- UNSAFE_OR_UNVERIFIED_LOCATION: `364`
- HIGHSEC_RESTRICTED_CAPITAL: `65`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `5`
- LIST_DATA_INCOMPLETE: `5`
- FATAL_OR_ACCESS_UNVERIFIED: `4`
- LIST_TOO_SLOW: `4`
