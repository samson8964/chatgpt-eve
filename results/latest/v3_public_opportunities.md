# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T02:01:46.571Z
- Market snapshot: 2026-10-08T01:48:22.937Z
- Candidate universe: 24550; deep validation pool: 242; feasible: 181
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 154
- FORMAL MAIL: 4

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `49947`
- eligible_contracts: `43396`
- market_executable_contracts: `24550`
- snapshot_candidates: `24550`
- candidate_pool: `605`
- location_executable: `242`
- feasible: `181`
- full_cash: `5`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `154`
- mail_eligible: `4`

## Rejection reasons

- BPC_ROUTED: `18622`
- MARKET_INELIGIBLE_SINGLETON: `5989`
- UNSAFE_OR_UNVERIFIED_LOCATION: `363`
- HIGHSEC_RESTRICTED_CAPITAL: `58`
- FATAL_OR_ACCESS_UNVERIFIED: `13`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_DATA_INCOMPLETE: `3`
