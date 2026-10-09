# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T10:31:37.315Z
- Market snapshot: 2026-10-09T10:18:32.028Z
- Candidate universe: 24408; deep validation pool: 228; feasible: 161
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 146
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

- raw_contracts: `50265`
- eligible_contracts: `43549`
- market_executable_contracts: `24408`
- snapshot_candidates: `24408`
- candidate_pool: `610`
- location_executable: `228`
- feasible: `161`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `146`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18926`
- MARKET_INELIGIBLE_SINGLETON: `6241`
- UNSAFE_OR_UNVERIFIED_LOCATION: `382`
- HIGHSEC_RESTRICTED_CAPITAL: `62`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_DATA_INCOMPLETE: `5`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
- NO_EXECUTABLE_ITEMS: `2`
