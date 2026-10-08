# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T01:01:49.705Z
- Market snapshot: 2026-10-08T01:18:21.885Z
- Candidate universe: 24549; deep validation pool: 230; feasible: 211
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 156
- FORMAL MAIL: 3

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
- eligible_contracts: `43398`
- market_executable_contracts: `24549`
- snapshot_candidates: `24549`
- candidate_pool: `605`
- location_executable: `230`
- feasible: `211`
- full_cash: `5`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `156`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18623`
- MARKET_INELIGIBLE_SINGLETON: `6000`
- UNSAFE_OR_UNVERIFIED_LOCATION: `375`
- HIGHSEC_RESTRICTED_CAPITAL: `15`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
- LIST_DATA_INCOMPLETE: `2`
