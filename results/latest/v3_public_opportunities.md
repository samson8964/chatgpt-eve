# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T08:31:43.331Z
- Market snapshot: 2026-10-09T08:18:33.104Z
- Candidate universe: 24202; deep validation pool: 252; feasible: 229
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 157
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

- raw_contracts: `50080`
- eligible_contracts: `43310`
- market_executable_contracts: `24202`
- snapshot_candidates: `24202`
- candidate_pool: `608`
- location_executable: `252`
- feasible: `229`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `157`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18886`
- MARKET_INELIGIBLE_SINGLETON: `6044`
- UNSAFE_OR_UNVERIFIED_LOCATION: `356`
- HIGHSEC_RESTRICTED_CAPITAL: `20`
- FATAL_OR_ACCESS_UNVERIFIED: `13`
- LIST_TOO_SLOW: `5`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- SKIN_DOMINANT: `3`
- LIST_DATA_INCOMPLETE: `3`
