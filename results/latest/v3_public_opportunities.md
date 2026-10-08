# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T04:31:56.307Z
- Market snapshot: 2026-10-08T04:18:25.484Z
- Candidate universe: 24533; deep validation pool: 248; feasible: 244
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 3
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

- raw_contracts: `49858`
- eligible_contracts: `43327`
- market_executable_contracts: `24533`
- snapshot_candidates: `24533`
- candidate_pool: `605`
- location_executable: `248`
- feasible: `244`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `3`
- research_watch: `161`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18569`
- MARKET_INELIGIBLE_SINGLETON: `5986`
- UNSAFE_OR_UNVERIFIED_LOCATION: `357`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- FATAL_OR_ACCESS_UNVERIFIED: `4`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
- HIGHSEC_RESTRICTED_CAPITAL: `1`
