# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T01:01:48.384Z
- Market snapshot: 2026-10-11T01:18:37.250Z
- Candidate universe: 24611; deep validation pool: 269; feasible: 194
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 159
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

- raw_contracts: `50247`
- eligible_contracts: `43677`
- market_executable_contracts: `24611`
- snapshot_candidates: `24611`
- candidate_pool: `610`
- location_executable: `269`
- feasible: `194`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `159`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18844`
- MARKET_INELIGIBLE_SINGLETON: `6215`
- UNSAFE_OR_UNVERIFIED_LOCATION: `341`
- HIGHSEC_RESTRICTED_CAPITAL: `72`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
