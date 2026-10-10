# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T20:31:39.560Z
- Market snapshot: 2026-10-10T20:48:45.172Z
- Candidate universe: 24767; deep validation pool: 311; feasible: 241
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 162
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

- raw_contracts: `50461`
- eligible_contracts: `43808`
- market_executable_contracts: `24767`
- snapshot_candidates: `24767`
- candidate_pool: `610`
- location_executable: `311`
- feasible: `241`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `162`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18814`
- MARKET_INELIGIBLE_SINGLETON: `6324`
- UNSAFE_OR_UNVERIFIED_LOCATION: `299`
- HIGHSEC_RESTRICTED_CAPITAL: `67`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
- FATAL_OR_ACCESS_UNVERIFIED: `2`
