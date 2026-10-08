# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T13:01:55.055Z
- Market snapshot: 2026-10-08T12:49:02.748Z
- Candidate universe: 24569; deep validation pool: 259; feasible: 191
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 156
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

- raw_contracts: `49976`
- eligible_contracts: `43370`
- market_executable_contracts: `24569`
- snapshot_candidates: `24569`
- candidate_pool: `606`
- location_executable: `259`
- feasible: `191`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `156`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18577`
- MARKET_INELIGIBLE_SINGLETON: `6062`
- UNSAFE_OR_UNVERIFIED_LOCATION: `347`
- HIGHSEC_RESTRICTED_CAPITAL: `64`
- SKIN_DOMINANT: `4`
- FATAL_OR_ACCESS_UNVERIFIED: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
- LIST_TOO_SLOW: `2`
