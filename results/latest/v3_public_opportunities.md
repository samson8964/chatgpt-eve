# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T08:01:42.205Z
- Market snapshot: 2026-10-11T08:18:33.098Z
- Candidate universe: 24545; deep validation pool: 253; feasible: 179
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 158
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

- raw_contracts: `50225`
- eligible_contracts: `43763`
- market_executable_contracts: `24545`
- snapshot_candidates: `24545`
- candidate_pool: `610`
- location_executable: `253`
- feasible: `179`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `158`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18992`
- MARKET_INELIGIBLE_SINGLETON: `6256`
- UNSAFE_OR_UNVERIFIED_LOCATION: `357`
- HIGHSEC_RESTRICTED_CAPITAL: `69`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `5`
- FATAL_OR_ACCESS_UNVERIFIED: `3`
- LIST_DATA_INCOMPLETE: `3`
