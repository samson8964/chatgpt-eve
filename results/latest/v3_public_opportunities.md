# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T10:31:37.315Z
- Market snapshot: 2026-10-09T10:48:35.374Z
- Candidate universe: 24407; deep validation pool: 235; feasible: 173
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 154
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

- raw_contracts: `50265`
- eligible_contracts: `43546`
- market_executable_contracts: `24407`
- snapshot_candidates: `24407`
- candidate_pool: `610`
- location_executable: `235`
- feasible: `173`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `154`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18923`
- MARKET_INELIGIBLE_SINGLETON: `6243`
- UNSAFE_OR_UNVERIFIED_LOCATION: `375`
- HIGHSEC_RESTRICTED_CAPITAL: `57`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_DATA_INCOMPLETE: `5`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
- NO_EXECUTABLE_ITEMS: `2`
