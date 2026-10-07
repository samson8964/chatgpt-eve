# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T17:01:41.812Z
- Market snapshot: 2026-10-07T16:48:28.061Z
- Candidate universe: 24473; deep validation pool: 247; feasible: 186
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 153
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

- raw_contracts: `49726`
- eligible_contracts: `43197`
- market_executable_contracts: `24473`
- snapshot_candidates: `24473`
- candidate_pool: `605`
- location_executable: `247`
- feasible: `186`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `153`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18507`
- MARKET_INELIGIBLE_SINGLETON: `6007`
- UNSAFE_OR_UNVERIFIED_LOCATION: `358`
- HIGHSEC_RESTRICTED_CAPITAL: `56`
- FATAL_OR_ACCESS_UNVERIFIED: `17`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
- NO_EXECUTABLE_ITEMS: `2`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
- LIST_DATA_INCOMPLETE: `2`
