# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-13T00:01:41.131Z
- Market snapshot: 2026-10-12T23:48:40.164Z
- Candidate universe: 25089; deep validation pool: 277; feasible: 167
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 147
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

- raw_contracts: `50741`
- eligible_contracts: `44468`
- market_executable_contracts: `25089`
- snapshot_candidates: `25089`
- candidate_pool: `612`
- location_executable: `277`
- feasible: `167`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `147`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `19148`
- MARKET_INELIGIBLE_SINGLETON: `6481`
- UNSAFE_OR_UNVERIFIED_LOCATION: `335`
- HIGHSEC_RESTRICTED_CAPITAL: `107`
- FATAL_OR_ACCESS_UNVERIFIED: `13`
- LIST_DATA_INCOMPLETE: `10`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_TOO_SLOW: `6`
- SKIN_DOMINANT: `3`
