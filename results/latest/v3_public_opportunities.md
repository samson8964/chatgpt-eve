# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T13:31:25.005Z
- Market snapshot: 2026-10-07T13:48:28.028Z
- Candidate universe: 24530; deep validation pool: 257; feasible: 190
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 158
- FORMAL MAIL: 0

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `49791`
- eligible_contracts: `43192`
- market_executable_contracts: `24530`
- snapshot_candidates: `24530`
- candidate_pool: `605`
- location_executable: `257`
- feasible: `190`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `158`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18440`
- MARKET_INELIGIBLE_SINGLETON: `5989`
- UNSAFE_OR_UNVERIFIED_LOCATION: `348`
- HIGHSEC_RESTRICTED_CAPITAL: `63`
- FATAL_OR_ACCESS_UNVERIFIED: `20`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
