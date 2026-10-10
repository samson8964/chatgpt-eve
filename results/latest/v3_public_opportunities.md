# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T08:31:37.209Z
- Market snapshot: 2026-10-10T08:18:26.940Z
- Candidate universe: 24689; deep validation pool: 255; feasible: 179
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 154
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

- raw_contracts: `50370`
- eligible_contracts: `43733`
- market_executable_contracts: `24689`
- snapshot_candidates: `24689`
- candidate_pool: `610`
- location_executable: `255`
- feasible: `179`
- full_cash: `1`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `11`
- research_watch: `154`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18829`
- MARKET_INELIGIBLE_SINGLETON: `6270`
- UNSAFE_OR_UNVERIFIED_LOCATION: `355`
- HIGHSEC_RESTRICTED_CAPITAL: `70`
- FATAL_OR_ACCESS_UNVERIFIED: `12`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_DATA_INCOMPLETE: `5`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `3`
- NO_EXECUTABLE_ITEMS: `2`
