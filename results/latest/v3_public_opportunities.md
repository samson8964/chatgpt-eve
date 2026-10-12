# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T00:01:39.565Z
- Market snapshot: 2026-10-12T00:18:35.095Z
- Candidate universe: 24848; deep validation pool: 260; feasible: 186
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 161
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

- raw_contracts: `50874`
- eligible_contracts: `44151`
- market_executable_contracts: `24848`
- snapshot_candidates: `24848`
- candidate_pool: `612`
- location_executable: `260`
- feasible: `186`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `161`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19066`
- MARKET_INELIGIBLE_SINGLETON: `6467`
- UNSAFE_OR_UNVERIFIED_LOCATION: `352`
- HIGHSEC_RESTRICTED_CAPITAL: `69`
- BARTER_PROCUREMENT_INCOMPLETE: `9`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `4`
- FATAL_OR_ACCESS_UNVERIFIED: `3`
- LIST_DATA_INCOMPLETE: `2`
