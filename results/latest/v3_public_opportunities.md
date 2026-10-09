# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T15:01:31.904Z
- Market snapshot: 2026-10-09T15:18:37.479Z
- Candidate universe: 24434; deep validation pool: 270; feasible: 199
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 161
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

- raw_contracts: `50239`
- eligible_contracts: `43535`
- market_executable_contracts: `24434`
- snapshot_candidates: `24434`
- candidate_pool: `610`
- location_executable: `270`
- feasible: `199`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `161`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18882`
- MARKET_INELIGIBLE_SINGLETON: `6206`
- UNSAFE_OR_UNVERIFIED_LOCATION: `340`
- HIGHSEC_RESTRICTED_CAPITAL: `67`
- FATAL_OR_ACCESS_UNVERIFIED: `16`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
