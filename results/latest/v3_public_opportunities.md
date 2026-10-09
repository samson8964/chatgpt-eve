# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T16:31:25.182Z
- Market snapshot: 2026-10-09T16:18:35.491Z
- Candidate universe: 24394; deep validation pool: 268; feasible: 247
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 158
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

- raw_contracts: `50218`
- eligible_contracts: `43556`
- market_executable_contracts: `24394`
- snapshot_candidates: `24394`
- candidate_pool: `610`
- location_executable: `268`
- feasible: `247`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `158`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18952`
- MARKET_INELIGIBLE_SINGLETON: `6184`
- UNSAFE_OR_UNVERIFIED_LOCATION: `342`
- HIGHSEC_RESTRICTED_CAPITAL: `18`
- FATAL_OR_ACCESS_UNVERIFIED: `12`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
- LIST_UNSUPPORTED: `1`
