# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T20:31:56.089Z
- Market snapshot: 2026-10-07T20:18:22.770Z
- Candidate universe: 24548; deep validation pool: 222; feasible: 155
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 142
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

- raw_contracts: `49935`
- eligible_contracts: `43381`
- market_executable_contracts: `24548`
- snapshot_candidates: `24548`
- candidate_pool: `605`
- location_executable: `222`
- feasible: `155`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `142`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18608`
- MARKET_INELIGIBLE_SINGLETON: `6005`
- UNSAFE_OR_UNVERIFIED_LOCATION: `383`
- HIGHSEC_RESTRICTED_CAPITAL: `63`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
