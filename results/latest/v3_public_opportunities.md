# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T23:01:40.490Z
- Market snapshot: 2026-10-07T22:48:26.492Z
- Candidate universe: 24530; deep validation pool: 220; feasible: 156
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 131
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

- raw_contracts: `49945`
- eligible_contracts: `43373`
- market_executable_contracts: `24530`
- snapshot_candidates: `24530`
- candidate_pool: `605`
- location_executable: `220`
- feasible: `156`
- full_cash: `5`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `131`
- mail_eligible: `4`

## Rejection reasons

- BPC_ROUTED: `18620`
- MARKET_INELIGIBLE_SINGLETON: `5988`
- UNSAFE_OR_UNVERIFIED_LOCATION: `385`
- HIGHSEC_RESTRICTED_CAPITAL: `60`
- FATAL_OR_ACCESS_UNVERIFIED: `11`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
