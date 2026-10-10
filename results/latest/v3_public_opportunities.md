# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T09:31:38.357Z
- Market snapshot: 2026-10-10T09:18:29.126Z
- Candidate universe: 24631; deep validation pool: 263; feasible: 189
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 159
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

- raw_contracts: `50406`
- eligible_contracts: `43721`
- market_executable_contracts: `24631`
- snapshot_candidates: `24631`
- candidate_pool: `611`
- location_executable: `263`
- feasible: `189`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `159`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18875`
- MARKET_INELIGIBLE_SINGLETON: `6270`
- UNSAFE_OR_UNVERIFIED_LOCATION: `348`
- HIGHSEC_RESTRICTED_CAPITAL: `67`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `4`
- NO_EXECUTABLE_ITEMS: `2`
